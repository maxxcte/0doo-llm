from openai import OpenAI
import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    @api.model
    def _get_available_services(self):
        services = super()._get_available_services()
        return services + [("openai", "OpenAI")]

    def openai_get_client(self):
        """Get OpenAI client instance"""
        return OpenAI(api_key=self.api_key, base_url=self.api_base or None)

    def get_available_tools(self, tool_ids=None):
        """Get available tools for this provider

        Args:
            tool_ids: Optional specific tool ids to include

        Returns:
            List of tool definitions in the format expected by the provider
        """
        domain = [("active", "=", True)]

        if tool_ids:
            domain.append(("id", "in", tool_ids))
        else:
            # Include default tools if no specific tools requested
            domain.append(("default", "=", True))

        tools = self.env["llm.tool"].search(domain)
        return tools
        
    # OpenAI specific implementation
    def openai_format_tools(self, tools):
        """Format tools for OpenAI"""
        return [tool.to_tool_definition() for tool in tools]

    def openai_chat(
        self, messages, model=None, stream=False, tools=None, tool_choice="auto", thread=None
    ):
        """Send chat messages using OpenAI with tools support"""
        model = self.get_model(model, "chat")

        # Prepare request parameters
        params = self._prepare_openai_params(
            model, messages, stream, tools, tool_choice
        )

        # Make the API call
        response = self.client.chat.completions.create(**params)

        # Process the response based on streaming mode
        if not stream:
            return self._process_non_streaming_response(response, thread)
        else:
            return self._process_streaming_response(response, thread)

    def _prepare_openai_params(self, model, messages, stream, tools, tool_choice):
        """Prepare parameters for OpenAI API call"""
        params = {
            "model": model.name,
            "messages": messages.copy(),  # Create a copy to avoid modifying the original
            "stream": stream,
        }

        # Add tools if specified
        if tools:
            tool_objects = self.get_available_tools(tools)
            formatted_tools = self.format_tools_for_provider(tool_objects)

            if formatted_tools:
                params["tools"] = formatted_tools
                params["tool_choice"] = tool_choice

                # Check if any tools require consent
                consent_required_tools = tool_objects.filtered(
                    lambda t: t.requires_user_consent
                )

                # Only add consent instructions if there are tools requiring consent
                if consent_required_tools:
                    # Get names of tools requiring consent for more specific instructions
                    consent_tool_names = ", ".join(
                        [f"'{t.name}'" for t in consent_required_tools]
                    )

                    # Get consent message template from config
                    config = self.env["llm.tool.consent.config"].get_active_config()
                    consent_instruction = config.system_message_template.format(
                        tool_names=consent_tool_names
                    )

                    # Check if a system message already exists
                    has_system_message = False
                    for msg in params["messages"]:
                        if msg.get("role") == "system":
                            # Add to existing system message
                            msg["content"] += f"\n\n{consent_instruction}"
                            has_system_message = True
                            break

                    # If no system message exists, add one
                    if not has_system_message:
                        # Insert system message at the beginning
                        params["messages"].insert(
                            0, {"role": "system", "content": consent_instruction}
                        )

        return params

    def _process_non_streaming_response(self, response, thread=None):
        """Process a non-streaming response from OpenAI"""
        message = {
            "role": response.choices[0].message.role,
            "content": response.choices[0].message.content or "",  # Handle None content
        }

        # Handle tool calls if present
        if (
            hasattr(response.choices[0].message, "tool_calls")
            and response.choices[0].message.tool_calls
        ):
            message["tool_calls"] = []

            for tool_call in response.choices[0].message.tool_calls:
                if thread:
                    tool_result = thread.process_tool_call(
                        tool_call.function.name, tool_call.function.arguments, tool_call.id
                    )
                else:
                    tool_result = self._execute_tool(
                        tool_call.function.name, tool_call.function.arguments, tool_call.id
                    )
                message["tool_calls"].append(tool_result)

        yield message

    def _process_streaming_response(self, response, thread=None):
        """Process a streaming response from OpenAI"""
        tool_call_chunks = {}

        for chunk in response:
            delta = chunk.choices[0].delta

            # Handle normal content
            if hasattr(delta, "content") and delta.content is not None:
                yield {
                    "role": "assistant",
                    "content": delta.content,
                }

            # Handle streaming tool calls
            if hasattr(delta, "tool_calls") and delta.tool_calls:
                for tool_call_chunk in delta.tool_calls:
                    index = tool_call_chunk.index

                    # Initialize or update tool call data
                    tool_call_chunks = self._update_tool_call_chunk(
                        tool_call_chunks, tool_call_chunk, index
                    )

                    # Check if we have a complete tool call
                    current_args = tool_call_chunks[index]["function"]["arguments"]
                    if current_args and current_args.endswith("}"):
                        try:
                            # Validate JSON is complete by parsing it
                            json.loads(current_args)

                            # Get tool name
                            tool_name = tool_call_chunks[index]["function"]["name"]
                            if not tool_name:
                                _logger.warning(f"Empty tool name for index: {index}")
                                continue

                            # Execute the tool and yield result
                            tool_id = tool_call_chunks[index]["id"]
                            
                            if thread:
                                tool_result = thread.process_tool_call(
                                    tool_name, current_args, tool_id
                                )
                            else:
                                tool_result = self._execute_tool(
                                    tool_name, current_args, tool_id
                                )

                            # Add result to tool call data
                            tool_call_chunks[index]["result"] = tool_result["result"]

                            # Yield the tool call with result
                            yield {
                                "role": "assistant",
                                "tool_call": tool_call_chunks[index],
                            }
                        except json.JSONDecodeError:
                            # JSON not complete yet, continue accumulating
                            _logger.info(
                                "JSON arguments incomplete, continuing to accumulate"
                            )
                        except Exception as e:
                            self._handle_tool_execution_error(
                                e, tool_call_chunks, index
                            )
                            yield {
                                "role": "assistant",
                                "tool_call": tool_call_chunks[index],
                            }

    def _update_tool_call_chunk(self, tool_call_chunks, tool_call_chunk, index):
        """Update tool call chunks with new data"""
        # Initialize tool call data if it's a new one
        if index not in tool_call_chunks:
            tool_call_chunks[index] = {
                "id": tool_call_chunk.id,
                "type": "function",
                "function": {"name": "", "arguments": ""},
            }

        # First chunk typically contains id, name and type
        if tool_call_chunk.id:
            tool_call_chunks[index]["id"] = tool_call_chunk.id

        if tool_call_chunk.type:
            tool_call_chunks[index]["type"] = tool_call_chunk.type

        # Update function name if present
        if (
            hasattr(tool_call_chunk, "function")
            and hasattr(tool_call_chunk.function, "name")
            and tool_call_chunk.function.name
        ):
            tool_call_chunks[index]["function"]["name"] = tool_call_chunk.function.name

        # Update arguments if present - this continues across multiple chunks
        if (
            hasattr(tool_call_chunk, "function")
            and hasattr(tool_call_chunk.function, "arguments")
            and tool_call_chunk.function.arguments is not None
        ):
            arg_chunk = tool_call_chunk.function.arguments
            tool_call_chunks[index]["function"]["arguments"] += arg_chunk

        return tool_call_chunks

    def _execute_tool(self, tool_name, arguments_str, tool_id):
        """Execute a tool and return the result"""
        tool = self.env["llm.tool"].search([("name", "=", tool_name)], limit=1)

        if not tool:
            _logger.error(f"Tool '{tool_name}' not found")
            return {
                "id": tool_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": arguments_str,
                },
                "result": json.dumps({"error": f"Tool '{tool_name}' not found"}),
            }

        try:
            arguments = json.loads(arguments_str)
            result = tool.execute(arguments)

            return {
                "id": tool_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": arguments_str,
                },
                "result": json.dumps(result),
            }
        except Exception as e:
            _logger.exception(f"Error executing tool {tool_name}: {str(e)}")
            return {
                "id": tool_id,
                "type": "function",
                "function": {
                    "name": tool_name,
                    "arguments": arguments_str,
                },
                "result": json.dumps({"error": str(e)}),
            }

    def _handle_tool_execution_error(self, error, tool_call_chunks, index):
        """Handle errors during tool execution"""
        _logger.exception(f"Error executing tool: {str(error)}")
        tool_call_chunks[index]["result"] = json.dumps({"error": str(error)})

    def openai_embedding(self, texts, model=None):
        """Generate embeddings using OpenAI"""
        model = self.get_model(model, "embedding")

        response = self.client.embeddings.create(model=model.name, input=texts)
        return [r.embedding for r in response.data]

    def openai_models(self):
        """List available OpenAI models"""
        models = self.client.models.list()

        for model in models.data:
            # Map model capabilities based on model ID patterns
            capabilities = ["chat"]  # default
            if "text-embedding" in model.id:
                capabilities = ["embedding"]
            elif "gpt-4-vision" in model.id:
                capabilities = ["chat", "multimodal"]

            yield {
                "name": model.id,
                "details": {
                    "id": model.id,
                    "capabilities": capabilities,
                    **model.model_dump(),
                },
            }

    def chat(self, messages, model=None, stream=False, tools=None, tool_choice="auto", thread=None):
        """Send chat messages using this provider"""
        return self._dispatch(
            "chat",
            messages,
            model=model,
            stream=stream,
            tools=tools,
            tool_choice=tool_choice,
            thread=thread,
        )
