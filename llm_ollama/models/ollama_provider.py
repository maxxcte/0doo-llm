import ollama
import json
import logging

from odoo import api, models
_logger = logging.getLogger(__name__)

class LLMProvider(models.Model):
    _inherit = "llm.provider"

    @api.model
    def _get_available_services(self):
        services = super()._get_available_services()
        return services + [("ollama", "Ollama")]

    def ollama_get_client(self):
        """Get Ollama client instance"""
        return ollama.Client(host=self.api_base or "http://localhost:11434")

    # Ollama specific implementation
    def ollama_format_tools(self, tools):
        """Format tools for Ollama"""
        return [self._ollama_format_tool(tool) for tool in tools]

    def _ollama_format_tool(self, tool):
        """Convert a tool to Ollama format

        Args:
            tool: llm.tool record to convert

        Returns:
            Dictionary in Ollama tool format
        """
        # First try to use overridden schema if available
        if tool.override_tool_schema and tool.overriden_schema:
            try:
                schema = json.loads(tool.overriden_schema)
                return self._create_ollama_tool_from_schema(schema, tool)
            except json.JSONDecodeError:
                _logger.error(f"Invalid JSON schema for tool {tool.name}")
                # Continue to next approach

        # Next try to use Pydantic model
        try:
            pydantic_model = tool.get_pydantic_model()
            if pydantic_model:
                # Get schema directly from Pydantic model
                model_schema = pydantic_model.model_json_schema()
                return self._create_ollama_tool_from_schema(model_schema, tool)
        except Exception as e:
            _logger.error(f"Error using Pydantic model for {tool.name}: {str(e)}")
            # Continue to fallback approach

        # Fallback to using the stored schema
        try:
            schema = json.loads(tool.schema)
            return self._create_ollama_tool_from_schema(schema, tool)
        except json.JSONDecodeError:
            _logger.error(f"Invalid JSON schema for tool {tool.name}")
            # Use minimal fallback schema
            schema = {
                "title": tool.name,
                "description": tool.description,
                "properties": {},
            }
            return self._create_ollama_tool_from_schema(schema, tool)

    def _create_ollama_tool_from_schema(self, schema, tool):
        """Helper method to create an Ollama tool from a schema

        Args:
            schema: JSON schema dictionary
            tool: llm.tool record

        Returns:
            Dictionary in Ollama tool format
        """
        formatted_tool = {
            "type": "function",
            "function": {
                "name": schema.get("title", tool.name),
                "description": tool.description
                if tool.override_tool_description
                else schema.get("description", ""),
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        }

        return formatted_tool

    def ollama_chat(
        self,
        messages,
        model=None,
        stream=False,
        tools=None,
        **kwargs
    ):
        """Send chat messages using Ollama with tools support"""
        model = self.get_model(model, "chat")

        # Prepare request parameters
        params = self._prepare_ollama_chat_params(
            model, messages, stream, tools=tools
        )

        # Make the API call
        response = self.client.chat(**params)

        # Process the response based on streaming mode
        if not stream:
            return self.ollama_process_non_streaming_response(response)
        else:
            return self.ollama_process_streaming_response(response)

    def _prepare_ollama_chat_params(self, model, messages, stream, tools):
        """Prepare parameters for Ollama API call"""
        params = {
            "model": model.name,
            "messages": messages.copy(),  # Create a copy to avoid modifying the original
            "stream": stream,
        }

        # Add tools if specified
        if tools:
            formatted_tools = self.ollama_format_tools(tools)

            if formatted_tools:
                params["tools"] = formatted_tools

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

    def ollama_process_non_streaming_response(self, response):
        """Process a non-streaming response from Ollama"""
        message = {
            "role": "assistant",
            "content": response["message"]["content"] or "",  # Handle None content
        }

        # Handle tool calls if present
        if (
            "tool_calls" in response["message"]
            and response["message"]["tool_calls"]
        ):
            message["tool_calls"] = []

            for tool_call in response["message"]["tool_calls"]:
                # Return the tool call without executing it
                tool_call_data = {
                    "id": tool_call.get("id", ""),
                    "type": "function",
                    "function": {
                        "name": tool_call["function"]["name"],
                        "arguments": "",
                    },
                }
                
                # Handle different types of arguments
                if "function" in tool_call and "arguments" in tool_call["function"]:
                    arguments = tool_call["function"]["arguments"]
                    if isinstance(arguments, dict):
                        tool_call_data["function"]["arguments"] = json.dumps(arguments)
                    elif isinstance(arguments, str):
                        tool_call_data["function"]["arguments"] = arguments
                    else:
                        # For any other type, convert to string via JSON
                        try:
                            tool_call_data["function"]["arguments"] = json.dumps(arguments)
                        except (TypeError, ValueError):
                            _logger.warning(f"Could not serialize arguments of type {type(arguments)}")
                            tool_call_data["function"]["arguments"] = str(arguments)
                
                message["tool_calls"].append(tool_call_data)

        yield message

    def ollama_process_streaming_response(self, response):
        """Process a streaming response from Ollama"""
        tool_call_chunks = {}
        last_content = ""

        for chunk in response:
            # Debug log the chunk structure
            _logger.info(f"Ollama streaming chunk: {chunk}")
            
            # Handle normal content
            if "message" in chunk and "content" in chunk["message"] and chunk["message"]["content"]:
                content = chunk["message"]["content"]
                # Only yield if there's new content
                if content != last_content:
                    last_content = content
                    yield {
                        "role": "assistant",
                        "content": content,
                    }

            # Handle tool calls
            if "message" in chunk and "tool_calls" in chunk["message"] and chunk["message"]["tool_calls"]:
                for i, tool_call in enumerate(chunk["message"]["tool_calls"]):
                    # Use the index from the loop if not provided in the response
                    index = tool_call.get("index", i)
                    
                    # Initialize tool call data if it doesn't exist
                    if index not in tool_call_chunks:
                        tool_call_chunks[index] = {
                            "id": tool_call.get("id", f"call_{index}"),
                            "type": "function",
                            "function": {
                                "name": tool_call["function"]["name"],
                                "arguments": "",
                            },
                        }
                    
                    # Update arguments
                    if "arguments" in tool_call["function"]:
                        arguments = tool_call["function"]["arguments"]
                        
                        # Handle different argument types, but always store as JSON string
                        # for consistency with llm_thread module
                        if isinstance(arguments, dict):
                            # Convert dictionary to JSON string
                            tool_call_chunks[index]["function"]["arguments"] = json.dumps(arguments)
                        elif isinstance(arguments, str):
                            # If it's already a string, check if it's valid JSON
                            try:
                                # Parse and re-stringify to ensure consistent formatting
                                parsed = json.loads(arguments)
                                tool_call_chunks[index]["function"]["arguments"] = json.dumps(parsed)
                            except json.JSONDecodeError:
                                # If it's not valid JSON, use as is (might be plain text)
                                tool_call_chunks[index]["function"]["arguments"] = arguments
                                _logger.warning(f"Received string arguments that aren't valid JSON: {arguments}")
                        else:
                            # For any other type, try to convert to JSON string
                            try:
                                tool_call_chunks[index]["function"]["arguments"] = json.dumps(arguments)
                            except (TypeError, ValueError):
                                # If conversion fails, use string representation
                                tool_call_chunks[index]["function"]["arguments"] = str(arguments)
                                _logger.warning(f"Couldn't convert arguments to JSON: {type(arguments)}")
                    
                    # Yield the tool call
                    yield {
                        "role": "assistant",
                        "tool_call": tool_call_chunks[index],
                    }
            
            # If this is the final chunk (done=True), make sure we've yielded all tool calls
            if chunk.get("done", False) and tool_call_chunks:
                # We've already yielded the tool calls above, so we don't need to do anything here
                pass

    def ollama_embedding(self, texts, model=None):
        """Generate embeddings using Ollama"""
        model = self.get_model(model, "embedding")

        # Ensure texts is a list
        if isinstance(texts, str):
            texts = [texts]

        # Get embeddings for each text
        embeddings = []
        for text in texts:
            response = self.client.embeddings(model=model.name, prompt=text)
            embeddings.append(response["embedding"])

        return embeddings

    def ollama_models(self):
        """List available Ollama models"""
        response = self.client.list()

        for model in response.get("models", []):
            # Basic model info
            model_info = {
                "name": model["name"],
                "details": {
                    "id": model["name"],
                    "capabilities": ["chat"],  # Default capability
                    "modified_at": model.get("modified_at"),
                    "size": model.get("size"),
                    "digest": model.get("digest"),
                },
            }

            # Add embedding capability if model name suggests it
            if "embedding" in model["name"].lower():
                model_info["details"]["capabilities"].append("embedding")

            yield model_info

    def ollama_format_messages(self, messages, system_prompt=None):
        """Format messages for Ollama API

        Args:
            messages: mail.message recordset to format
            system_prompt: Optional system prompt to include at the beginning of the messages

        Returns:
            List of formatted messages in Ollama-compatible format
        """
        # First use the default implementation from the llm_tool module
        formatted_messages = []

        # Add system prompt if provided
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        # Format the rest of the messages
        for message in messages:
            formatted_messages.append(self._format_message_for_ollama(message))

        return formatted_messages

    def _format_message_for_ollama(self, message):
        # Check if this is a tool message
        if message.subtype_id and message.tool_call_id:
            tool_message_subtype = self.env.ref("llm_tool.mt_tool_message")
            _logger.info("Tool Message %s", message)
            if message.subtype_id.id == tool_message_subtype.id:
                return {
                    "role": "tool",
                    "name": "odoo_record_retriever",
                    "content": message.body or "",  # Ensure content is never null
                }

        # Check if this is an assistant message with tool calls
        if not message.author_id and message.tool_calls:
            try:
                tool_calls_data = json.loads(message.tool_calls)
                _logger.info("Tool Calls %s", tool_calls_data)
                
                # Process each tool call to ensure arguments are properly formatted
                for tool_call in tool_calls_data:
                    if "function" in tool_call and "arguments" in tool_call["function"]:
                        # If arguments are a string that looks like JSON, parse it to a dict
                        args = tool_call["function"]["arguments"]
                        if isinstance(args, str) and args.strip().startswith("{") and args.strip().endswith("}"):
                            try:
                                tool_call["function"]["arguments"] = json.loads(args)
                            except json.JSONDecodeError:
                                _logger.warning(f"Could not parse tool call arguments as JSON: {args}")
                
                return {
                    "role": "assistant",
                    "content": message.body or "",  # Ensure content is never null
                    "tool_calls": tool_calls_data,
                }
            except (json.JSONDecodeError, ValueError) as e:
                # If JSON parsing fails, log the error and fall back to default behavior
                _logger.error(f"Error parsing tool calls: {str(e)}")
                pass

        # Default behavior from parent
        return self._default_format_message(message)
