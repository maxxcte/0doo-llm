import json
import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    @api.model
    def _is_tool_call_complete(self, function_data, expected_endings=("]", "}")):
        tool_name = function_data.get("name")
        args_str = function_data.get("arguments", "").strip()

        if not tool_name or not args_str:
            return False

        try:
            json.loads(args_str)
            if args_str.endswith(expected_endings):
                return True
        except json.JSONDecodeError:
            pass

        return False

    def _prepare_chat_params(
        self, model, messages, stream, tools, system_prompt, **kwargs
    ):
        """Generic method to prepare chat parameters for API call."""
        params = {
            "model": model.name,
            "stream": stream,
        }

        _logger.info(f"Preparing chat parameters: {kwargs}")

        messages = messages or []
        system_prompt = system_prompt or None

        if messages or system_prompt:
            formatted_messages = self.format_messages(messages, system_prompt)
            params["messages"] = formatted_messages

        if tools:
            formatted_tools = self.format_tools(tools)
            if formatted_tools:
                params["tools"] = formatted_tools
                if "tool_choice" in kwargs:
                    params["tool_choice"] = kwargs["tool_choice"]

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

                    if "messages" not in params:
                        params["messages"] = []

                    has_system_message = False
                    for msg in params["messages"]:
                        if msg.get("role") == "system":
                            existing_content = msg.get("content", "")
                            separator = "\n\n" if existing_content else ""
                            msg["content"] = (
                                f"{existing_content}{separator}{consent_instruction}"
                            )
                            has_system_message = True
                            break

                    if not has_system_message:
                        params["messages"].insert(
                            0, {"role": "system", "content": consent_instruction}
                        )

        return params
