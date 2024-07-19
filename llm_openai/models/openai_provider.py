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
            if tool.input_schema:
                try:
                    schema = json.loads(tool.input_schema)
                    return self._create_openai_tool_from_schema(schema, tool)
                except json.JSONDecodeError:
                    _logger.error(f"Invalid JSON schema for tool {tool.name}")

            schema = tool.get_input_schema()
            if schema:
                return self._create_openai_tool_from_schema(schema, tool)

            _logger.warning(
                f"Could not get schema for tool {tool.name}, using fallback"
            )
            schema = {"type": "object", "properties": {}, "required": []}
            return self._create_openai_tool_from_schema(schema, tool)

        except Exception as e:
            _logger.error(f"Error formatting tool {tool.name}: {str(e)}")
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

        if "items" in schema_node and isinstance(schema_node["items"], dict):
            items_dict = schema_node["items"]
            if "type" not in items_dict:
                items_dict["type"] = "string"
            self._recursively_patch_schema_items(items_dict)

        if "properties" in schema_node and isinstance(schema_node["properties"], dict):
            for prop_schema in schema_node["properties"].values():
                self._recursively_patch_schema_items(prop_schema)

        for combiner in ["anyOf", "allOf", "oneOf"]:
            if combiner in schema_node and isinstance(schema_node[combiner], list):
                for sub_schema in schema_node[combiner]:
                    self._recursively_patch_schema_items(sub_schema)

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

        # Ensure all nested 'items' have a 'type' for broader compatibility
        parameters_schema = schema  # Modify the schema directly before formatting
        self._recursively_patch_schema_items(parameters_schema)

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
        system_prompt=None,
    ):
        """Send chat messages using OpenAI with tools support"""
        model = self.get_model(model, "chat")

        # Prepare request parameters
        params = self._prepare_openai_chat_params(
            model, messages, stream, tools=tools, tool_choice=tool_choice, system_prompt=system_prompt
        )

        # Make the API call
        response = self.client.chat.completions.create(**params)

        # Process the response based on streaming mode
        if not stream:
            return self._openai_process_non_streaming_response(response)
        else:
            return self._openai_process_streaming_response(response)

    def _prepare_openai_chat_params(self, model, messages, stream, tools, tool_choice, system_prompt):
        """Prepare parameters for OpenAI API call"""
        params = {
            "model": model.name,
            "stream": stream,
        }

        messages = messages or []
        system_prompt = system_prompt or None

        if messages or system_prompt:
            formatted_messages = self.openai_format_messages(messages, system_prompt)
            params["messages"] = formatted_messages

        if tools:
            formatted_tools = self.openai_format_tools(tools)
            if formatted_tools:
                params["tools"] = formatted_tools
                params["tool_choice"] = tool_choice

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

    def _openai_process_non_streaming_response(self, response):
        """Processes OpenAI non-streamed response and returns ONE standardized dict."""
        _logger.info("Processing non-streaming OpenAI response.")
        try:
            choice = response.choices[0]
            message = choice.message
            result = {}

            if message.content:
                result['content'] = message.content

            if message.tool_calls:
                result['tool_calls'] = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                         }
                    } for tc in message.tool_calls
                ]

            if 'content' in result or 'tool_calls' in result:
                return result
            else:
                _logger.warning("OpenAI non-streaming response had no content or tool calls.")
                return {} # Return empty dict if nothing to process

        except (AttributeError, IndexError, Exception) as e:
            _logger.exception("Error processing OpenAI non-streaming response")
            return {'error': f"Error processing response: {e}"}

    def _openai_process_streaming_response(self, response_stream):
        """
        Processes OpenAI stream and yields standardized dicts for start_thread_loop.
        Yields: {'content': str} OR {'tool_calls': list} OR {'error': str}
        """
        assembled_tool_calls = {}
        final_tool_calls_list = []
        stream_has_tools = False
        finish_reason = None

        try:
            for chunk in response_stream:
                choice = chunk.choices[0] if chunk.choices else None
                delta = choice.delta if choice else None
                chunk_finish_reason = choice.finish_reason if choice else None
                if chunk_finish_reason:
                    finish_reason = chunk_finish_reason

                if not delta:
                    continue

                if delta.content:
                    yield {'content': delta.content}

                if delta.tool_calls:
                    stream_has_tools = True
                    # index can be null, so we use a counter as fallback
                    call_counter = 0
                    for tool_call_chunk in delta.tool_calls:
                        index = tool_call_chunk.index or call_counter
                        assembled_tool_calls = self._update_openai_tool_call_chunk(
                            assembled_tool_calls, tool_call_chunk, index
                        )
                        call_counter += 1
            if stream_has_tools:
                if finish_reason == 'tool_calls' or (finish_reason != 'error' and assembled_tool_calls):
                    for index, call_data in sorted(assembled_tool_calls.items()):
                        if call_data.get("_complete"):
                            tool_call_id = call_data.get("id").strip() or str(uuid.uuid4())
                            final_tool_calls_list.append({
                                # Generate a UUID for id if it's empty, google apis don't give tool call id for example
                                "id": tool_call_id,
                                "type": call_data.get("type", "function"), # Default type
                                "function": {
                                    "name": call_data["function"]["name"],
                                    "arguments": call_data["function"]["arguments"],
                                }
                            })
                        else:
                            yield {'error': f"Received incomplete tool call data from provider for tool index {index}."}

                    if final_tool_calls_list:
                        yield {'tool_calls': final_tool_calls_list}
                    elif assembled_tool_calls:
                         _logger.warning("Stream indicated tool calls, but none were successfully assembled.")

                elif finish_reason != 'error':
                     _logger.warning(f"OpenAI stream had tool chunks but finished with reason '{finish_reason}'. Not yielding tool calls.")

        except Exception as e:
            yield {'error': f"Internal error processing stream: {e}"}

    def _update_openai_tool_call_chunk(self, tool_call_chunks, tool_call_chunk, index):
        """
        Helper to assemble fragmented tool calls from OpenAI stream chunks.
        (Keep this helper as it's essential for stream processing)
        """
        if index not in tool_call_chunks:
            tool_call_chunks[index] = {
                "id": tool_call_chunk.id,
                "type": tool_call_chunk.type,
                "function": {"name": "", "arguments": ""},
                "_complete": False
            }

        current_call = tool_call_chunks[index]

        if tool_call_chunk.id:
            current_call["id"] = tool_call_chunk.id
        if tool_call_chunk.type:
            current_call["type"] = tool_call_chunk.type

        func_chunk = tool_call_chunk.function
        if func_chunk:
            if func_chunk.name:
                current_call["function"]["name"] = func_chunk.name
            if func_chunk.arguments:
                current_call["function"]["arguments"] += func_chunk.arguments

        if (current_call["function"].get("name") and
            current_call["function"]["arguments"].strip().endswith('}')):
            try:
                json.loads(current_call["function"]["arguments"])
                current_call["_complete"] = True
            except json.JSONDecodeError:
                current_call["_complete"] = False

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
            formatted_message = self._dispatch_on_message(message, "format_message")
            if formatted_message:
                formatted_messages.append(formatted_message)

        # Then validate and clean the messages for OpenAI
        return self._validate_and_clean_messages(formatted_messages)
