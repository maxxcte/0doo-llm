import json
import logging
import uuid

import ollama

from odoo import api, models

from ..utils.ollama_message_validator import OllamaMessageValidator
from ..utils.tool_id_utils import ToolIdUtils

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
        try:
            # First use the explicit input_schema if available
            if tool.input_schema:
                try:
                    schema = json.loads(tool.input_schema)
                    return self._create_ollama_tool_from_schema(schema, tool)
                except json.JSONDecodeError:
                    _logger.error(f"Invalid JSON schema for tool {tool.name}")
                    # Continue to next approach

            # Next generate schema from the tool's method signature
            schema = tool.get_input_schema()
            if schema:
                return self._create_ollama_tool_from_schema(schema, tool)

            # If we still don't have a schema, use minimal fallback
            _logger.warning(
                f"Could not get schema for tool {tool.name}, using fallback"
            )
            schema = {"type": "object", "properties": {}, "required": []}
            return self._create_ollama_tool_from_schema(schema, tool)

        except Exception as e:
            _logger.error(f"Error formatting tool {tool.name}: {str(e)}")
            # Use minimal fallback schema
            schema = {
                "title": tool.name,
                "description": tool.description,
                "properties": {},
                "required": [],
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
                "name": tool.name,
                "description": tool.description,
                "parameters": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            },
        }

        return formatted_tool

    def ollama_chat(self, messages, model=None, stream=False, tools=None, **kwargs):
        """Send chat messages using Ollama with tools support"""
        model = self.get_model(model, "chat")

        # Prepare request parameters
        params = self._prepare_ollama_chat_params(model, messages, stream, tools=tools)

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
        if "tool_calls" in response["message"] and response["message"]["tool_calls"]:
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
                            tool_call_data["function"]["arguments"] = json.dumps(
                                arguments
                            )
                        except (TypeError, ValueError):
                            _logger.warning(
                                f"Could not serialize arguments of type {type(arguments)}"
                            )
                            tool_call_data["function"]["arguments"] = str(arguments)

                message["tool_calls"].append(tool_call_data)

        yield message

    def ollama_process_streaming_response(self, response):
        """Process a streaming response from Ollama"""
        tool_call_chunks = {}
        last_content = ""

        for chunk in response:
            # Handle normal content
            if (
                "message" in chunk
                and "content" in chunk["message"]
                and chunk["message"]["content"]
            ):
                content = chunk["message"]["content"]
                # Only yield if there's new content
                if content != last_content:
                    last_content = content
                    yield {
                        "role": "assistant",
                        "content": content,
                    }

            # Handle tool calls
            if (
                "message" in chunk
                and "tool_calls" in chunk["message"]
                and chunk["message"]["tool_calls"]
            ):
                for i, tool_call in enumerate(chunk["message"]["tool_calls"]):
                    # Use the index from the loop if not provided in the response
                    index = tool_call.get("index", i)

                    # Get the tool name
                    tool_name = tool_call["function"]["name"]

                    # Generate a unique ID that includes the tool name
                    tool_id = ToolIdUtils.create_tool_id(tool_name, str(uuid.uuid4()))

                    # Initialize tool call data if it doesn't exist
                    if index not in tool_call_chunks:
                        tool_call_chunks[index] = {
                            "id": tool_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
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
                            tool_call_chunks[index]["function"]["arguments"] = (
                                json.dumps(arguments)
                            )
                        elif isinstance(arguments, str):
                            # If it's already a string, check if it's valid JSON
                            try:
                                # Parse and re-stringify to ensure consistent formatting
                                parsed = json.loads(arguments)
                                tool_call_chunks[index]["function"]["arguments"] = (
                                    json.dumps(parsed)
                                )
                            except json.JSONDecodeError:
                                # If it's not valid JSON, use as is (might be plain text)
                                tool_call_chunks[index]["function"]["arguments"] = (
                                    arguments
                                )
                                _logger.warning(
                                    f"Received string arguments that aren't valid JSON: {arguments}"
                                )
                        else:
                            # For any other type, try to convert to JSON string
                            try:
                                tool_call_chunks[index]["function"]["arguments"] = (
                                    json.dumps(arguments)
                                )
                            except (TypeError, ValueError):
                                # If conversion fails, use string representation
                                tool_call_chunks[index]["function"]["arguments"] = str(
                                    arguments
                                )
                                _logger.warning(
                                    f"Couldn't convert arguments to JSON: {type(arguments)}"
                                )

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
            response = self.client.embed(model=model.name, input=[text])
            embeddings.append(response["embeddings"][0])
        return embeddings

    def ollama_models(self):
        """List available Ollama models"""
        models_response = self.client.list()

        # Get models from the response
        if hasattr(models_response, "models"):
            models = models_response.models
        else:
            error_msg = f"Unexpected Ollama API response format: {models_response}"
            _logger.error(error_msg)
            raise ValueError(error_msg)

        for model in models:
            model_name = model.model

            model_info = {
                "name": model_name,
                "details": {
                    "id": model_name,
                    "capabilities": ["chat"],  # Default capability
                    "modified_at": str(model.modified_at)
                    if hasattr(model, "modified_at")
                    else None,
                    "size": model.size if hasattr(model, "size") else None,
                    "digest": model.digest if hasattr(model, "digest") else None,
                },
            }

            # Add embedding capability if model name suggests it
            if "embedding" in model_name.lower():
                model_info["details"]["capabilities"].append("embedding")

            yield model_info

    def ollama_format_messages(self, messages, system_prompt=None):
        """Format messages for Ollama API

        Args:
            messages: List of message records
            system_prompt: Optional system prompt to prepend

        Returns:
            List of formatted messages in Ollama format
        """
        # First use the default implementation from the llm_tool module
        formatted_messages = []

        # Add system prompt if provided
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        # Add all other messages, properly formatted
        for message in messages:
            formatted_msg = self._format_message_for_ollama(message)
            if formatted_msg is not None:
                formatted_messages.append(formatted_msg)

        # Validate and clean messages
        validator = OllamaMessageValidator(formatted_messages)
        return validator.validate_and_clean()