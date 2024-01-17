import json
import logging
import uuid

from openai import OpenAI

from odoo import api, models

from ..utils.openai_message_validator import OpenAIMessageValidator

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

    # OpenAI specific implementation
    def openai_format_tools(self, tools):
        """Format tools for OpenAI"""
        return [self._openai_format_tool(tool) for tool in tools]

    def _openai_format_tool(self, tool):
        """Convert a tool to OpenAI format

        Args:
            tool: llm.tool record to convert

        Returns:
            Dictionary in OpenAI tool format
        """
        try:
            # First use the explicit input_schema if available
            if tool.input_schema:
                try:
                    schema = json.loads(tool.input_schema)
                    return self._create_openai_tool_from_schema(schema, tool)
                except json.JSONDecodeError:
                    _logger.error(f"Invalid JSON schema for tool {tool.name}")
                    # Continue to next approach

            # Next generate schema from the tool's method signature
            schema = tool.get_input_schema()
            if schema:
                return self._create_openai_tool_from_schema(schema, tool)

            # If we still don't have a schema, use minimal fallback
            _logger.warning(
                f"Could not get schema for tool {tool.name}, using fallback"
            )
            schema = {"type": "object", "properties": {}, "required": []}
            return self._create_openai_tool_from_schema(schema, tool)

        except Exception as e:
            _logger.error(f"Error formatting tool {tool.name}: {str(e)}")
            # Use minimal fallback schema
            schema = {
                "title": tool.name,
                "description": tool.description,
                "properties": {},
                "required": [],
            }
            return self._create_openai_tool_from_schema(schema, tool)

    def _recursively_patch_schema_items(self, schema_node):
        """Recursively ensure 'items' dictionaries have a 'type' defined."""
        if not isinstance(schema_node, dict):
            return

        # Handle 'items' for arrays
        if "items" in schema_node and isinstance(schema_node["items"], dict):
            items_dict = schema_node["items"]
            if "type" not in items_dict:
                items_dict["type"] = "string"  # Default patch type
            # Recurse into items
            self._recursively_patch_schema_items(items_dict)

        # Handle 'properties' for objects
        if "properties" in schema_node and isinstance(schema_node["properties"], dict):
            for prop_schema in schema_node["properties"].values():
                self._recursively_patch_schema_items(prop_schema)

        # Handle schema combiners (anyOf, allOf, oneOf)
        for combiner in ["anyOf", "allOf", "oneOf"]:
            if combiner in schema_node and isinstance(schema_node[combiner], list):
                for sub_schema in schema_node[combiner]:
                    self._recursively_patch_schema_items(sub_schema)

        # Note: This doesn't handle every possible JSON schema structure,
        # but covers common cases like nested arrays and objects.

    def _create_openai_tool_from_schema(self, schema, tool):
        """Convert a JSON schema dictionary to an OpenAI tool format,
        patching missing item types recursively.
        Args:
            schema: JSON schema dictionary
            tool: llm.tool record

        Returns:
            Dictionary in OpenAI tool format
        """
        if not schema:
            _logger.warning(
                f"Could not generate schema for tool {tool.name}, skipping."
            )
            return None

        # --- Recursively Patch Schema --- START
        # Ensure all nested 'items' have a 'type' for broader compatibility
        parameters_schema = schema  # Modify the schema directly before formatting
        self._recursively_patch_schema_items(parameters_schema)
        # --- Recursively Patch Schema --- END

        # Format according to OpenAI requirements
        formatted_tool = {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": parameters_schema.get("properties", {}),
                    "required": parameters_schema.get("required", []),
                },
            },
        }

        return formatted_tool

    def openai_chat(
        self,
        messages,
        model=None,
        stream=False,
        tools=None,
        tool_choice="auto",
    ):
        """Send chat messages using OpenAI with tools support"""
        model = self.get_model(model, "chat")

        # Prepare request parameters
        params = self._prepare_openai_chat_params(
            model, messages, stream, tools=tools, tool_choice=tool_choice
        )

        # Make the API call
        response = self.client.chat.completions.create(**params)

        # Process the response based on streaming mode
        if not stream:
            return self._process_non_streaming_response(response)
        else:
            return self._process_streaming_response(response)

    def _prepare_openai_chat_params(self, model, messages, stream, tools, tool_choice):
        """Prepare parameters for OpenAI API call"""
        params = {
            "model": model.name,
            "messages": messages.copy(),  # Create a copy to avoid modifying the original
            "stream": stream,
        }

        # Add tools if specified
        if tools:
            formatted_tools = self.openai_format_tools(tools)
            if formatted_tools:
                params["tools"] = formatted_tools
                params["tool_choice"] = tool_choice

                # Check if any tools require consent
                consent_required_tools = tools.filtered(
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

    def _process_non_streaming_response(self, response):
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
                # Return the tool call without executing it
                tool_call_data = {
                    "id": tool_call.id,
                    "type": "function",
                    "function": {
                        "name": tool_call.function.name,
                        "arguments": tool_call.function.arguments,
                    },
                }
                message["tool_calls"].append(tool_call_data)

        yield message

    def _process_streaming_response(self, response):
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

                            # Generate a UUID for id if it's empty, google apis don't give tool call id for example
                            if not tool_call_chunks[index].get("id"):
                                tool_call_chunks[index]["id"] = str(uuid.uuid4())

                            # Yield the tool call without result
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
                            _logger.exception(f"Error processing tool call: {str(e)}")
                            # Add error to tool call data
                            tool_call_chunks[index]["error"] = str(e)

                            # Yield the tool call with error
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

    def chat(
        self,
        messages,
        model=None,
        stream=False,
        tools=None,
        tool_choice="auto",
    ):
        """Send chat messages using this provider"""
        return self._dispatch(
            "chat",
            messages,
            model=model,
            stream=stream,
            tools=tools,
            tool_choice=tool_choice,
        )

    def _validate_and_clean_messages(self, messages):
        """
        Validate and clean messages to ensure proper tool message structure for OpenAI.

        This method uses the OpenAIMessageValidator class to check that all tool messages
        have a preceding assistant message with matching tool_calls, and removes any
        tool messages that don't meet this requirement to avoid API errors.

        Args:
            messages (list): List of messages to validate and clean

        Returns:
            list: Cleaned list of messages
        """
        # Hardcoded value for verbose logging
        verbose_logging = False

        validator = OpenAIMessageValidator(
            messages, logger=_logger, verbose_logging=verbose_logging
        )
        return validator.validate_and_clean()

    def openai_format_messages(self, messages, system_prompt=None):
        """Format messages for OpenAI API

        Args:
            messages: mail.message recordset to format
            system_prompt: Optional system prompt to include at the beginning of the messages

        Returns:
            List of formatted messages in OpenAI-compatible format
        """
        # First use the default implementation from the llm_tool module
        formatted_messages = []

        # Add system prompt if provided
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        # Format the rest of the messages
        for message in messages:
            formatted_messages.append(self._format_message_for_openai(message))

        # Then validate and clean the messages for OpenAI
        return self._validate_and_clean_messages(formatted_messages)

    def _format_message_for_openai(self, message):
        # Check if this is a tool message
        if message.subtype_id and message.tool_call_id:
            tool_message_subtype = self.env.ref("llm_tool.mt_tool_message")
            if message.subtype_id.id == tool_message_subtype.id:
                return {
                    "role": "tool",
                    "tool_call_id": message.tool_call_id,
                    "content": message.body or "",  # Ensure content is never null
                }

        # Check if this is an assistant message with tool calls
        if not message.author_id and message.tool_calls:
            try:
                tool_calls_data = json.loads(message.tool_calls)
                result = {
                    "role": "assistant",
                    "tool_calls": tool_calls_data,
                }
                if message.body:
                    result["content"] = message.body
                return result
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, fall back to default behavior
                pass

        # Default behavior from parent
        return self._default_format_message(message)
