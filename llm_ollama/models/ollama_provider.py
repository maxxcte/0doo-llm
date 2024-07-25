import json
import logging
import uuid

import ollama

from odoo import api, models

from ..utils.ollama_message_validator import OllamaMessageValidator
from ..utils.ollama_tool_call_id_utils import OllamaToolCallIdUtils

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

    def ollama_chat(self, messages, model=None, stream=False, tools=None, system_prompt=None, **kwargs):
        """Send chat messages using Ollama with tools support"""
        model = self.get_model(model, "chat")

        params = self._prepare_ollama_chat_params(model, messages, stream, tools=tools, system_prompt=system_prompt)

        response = self.client.chat(**params)

        if not stream:
            return self.ollama_process_non_streaming_response(response)
        else:
            return self.ollama_process_streaming_response(response)

    def _prepare_ollama_chat_params(self, model, messages, stream, tools, system_prompt):
        """Prepare parameters for Ollama API call"""
        params = {
            "model": model.name,
            "stream": stream,
        }

        messages = messages or []
        system_prompt = system_prompt or None
        if messages or system_prompt:
            formatted_messages = self.ollama_format_messages(messages, system_prompt)
            params["messages"] = formatted_messages

        if tools:
            formatted_tools = self.ollama_format_tools(tools)

            if formatted_tools:
                params["tools"] = formatted_tools

                consent_required_tools = tools.filtered(
                    lambda t: t.requires_user_consent
                )

                if consent_required_tools:
                    consent_tool_names = ", ".join(
                        [f"'{t.name}'" for t in consent_required_tools]
                    )

                    config = self.env["llm.tool.consent.config"].get_active_config()
                    consent_instruction = config.system_message_template.format(
                        tool_names=consent_tool_names
                    )

                    has_system_message = False
                    for msg in params["messages"]:
                        if msg.get("role") == "system":
                            msg["content"] += f"\n\n{consent_instruction}"
                            has_system_message = True
                            break

                    if not has_system_message:
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

        if "tool_calls" in response["message"] and response["message"]["tool_calls"]:
            message["tool_calls"] = []

            for tool_call in response["message"]["tool_calls"]:
                tool_name = tool_call["function"]["name"]
                tool_id = OllamaToolCallIdUtils.create_tool_id(tool_name, str(uuid.uuid4()))

                tool_call_data = {
                    "id": tool_id,
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": "",
                    },
                }

                if "function" in tool_call and "arguments" in tool_call["function"]:
                    arguments = tool_call["function"]["arguments"]
                    if isinstance(arguments, dict):
                        tool_call_data["function"]["arguments"] = json.dumps(arguments)
                    elif isinstance(arguments, str):
                        tool_call_data["function"]["arguments"] = arguments
                    else:
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
        """
        Processes Ollama stream and yields standardized dicts.
        Yields: {'content': str} OR {'tool_calls': list} OR {'error': str}
        """
        assembled_tool_calls = {}
        final_tool_calls_list = []
        stream_has_tools = False
        is_done = False
        last_content = ""

        try:
            for chunk in response:
                if not chunk:
                    continue

                message = chunk.get("message", {})
                content_chunk = message.get("content")
                tool_calls_chunk = message.get("tool_calls")
                chunk_done = chunk.get("done", False)
                error_msg = chunk.get("error")

                if error_msg:
                    yield {'error': f"Ollama stream error: {error_msg}"}
                    return

                if chunk_done:
                    is_done = True

                if content_chunk is not None and content_chunk != last_content:
                    yield {'content': content_chunk}
                    last_content = content_chunk

                if tool_calls_chunk:
                    stream_has_tools = True
                    for i, tool_call_delta in enumerate(tool_calls_chunk):
                        assembled_tool_calls = self._ollama_update_tool_call_chunk(
                            assembled_tool_calls, tool_call_delta, i
                        )

            if stream_has_tools and is_done:
                for _, call_data in sorted(assembled_tool_calls.items()):
                    if call_data.get("_complete"):
                         tool_name = call_data["function"]["name"]
                         tool_id = OllamaToolCallIdUtils.create_tool_id(tool_name, str(uuid.uuid4()))
                         final_tool_calls_list.append({
                            "id": tool_id,
                            "type": "function",
                            "function": {
                                "name": tool_name,
                                "arguments": call_data["function"]["arguments"],
                            }
                         })

                if final_tool_calls_list:
                    yield {'tool_calls': final_tool_calls_list}

        except Exception as e:
            _logger.error(f"Error processing Ollama stream: {e}", exc_info=True)
            yield {'error': f"Internal error processing Ollama stream: {e}"}

    def _ollama_update_tool_call_chunk(self, assembled_tool_calls, tool_call_delta, index):
        """
        Helper to assemble tool calls from Ollama stream chunks.
        Ensures arguments are stored as a complete JSON string.
        """
        if index not in assembled_tool_calls:
            assembled_tool_calls[index] = {
                "id": None,
                "type": "function",
                "function": {"name": "", "arguments": ""},
                "_complete": False
            }

        current_call = assembled_tool_calls[index]
        func_delta = tool_call_delta.get("function", {})

        if func_delta.get("name"):
            current_call["function"]["name"] = func_delta["name"]

        if "arguments" in func_delta:
            new_args_part = func_delta["arguments"]
            if isinstance(new_args_part, dict):
                current_call["function"]["arguments"] = json.dumps(new_args_part)
            elif isinstance(new_args_part, str):
                current_call["function"]["arguments"] += new_args_part
            else:
                _logger.warning(f"Unexpected argument type in Ollama stream chunk: {type(new_args_part)}")

        # Use the common helper to determine completeness for Ollama
        current_call["_complete"] = self._is_tool_call_complete(
            current_call["function"], expected_endings=(']', '}')
        )
        return assembled_tool_calls

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
            formatted_msg = self._dispatch_on_message(message, "format_message")
            if formatted_msg is not None:
                formatted_messages.append(formatted_msg)

        # Validate and clean messages
        validator = OllamaMessageValidator(formatted_messages)
        return validator.validate_and_clean()