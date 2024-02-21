
import json
import logging

from odoo import models
from odoo.addons.llm_mail_message_subtypes.const import (
    LLM_TOOL_RESULT_SUBTYPE_XMLID,
    LLM_USER_SUBTYPE_XMLID,
    LLM_ASSISTANT_SUBTYPE_XMLID,
)

_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = "mail.message"

    def openai_format_message(self):
        """Provider-specific formatting for OpenAI."""
        self.ensure_one()
        user_subtype = self.env.ref(LLM_USER_SUBTYPE_XMLID, False)
        assistant_subtype = self.env.ref(LLM_ASSISTANT_SUBTYPE_XMLID, False)
        tool_result_subtype = self.env.ref(LLM_TOOL_RESULT_SUBTYPE_XMLID, False)

        subtype_id = self.subtype_id.id

        if user_subtype and subtype_id == user_subtype.id:
            return {'role': 'user', 'content': self.body or ""}

        elif assistant_subtype and subtype_id == assistant_subtype.id:
            entry = {'role': 'assistant', 'content': self.body or ""}
            api_tool_calls = None
            if self.tool_calls:
                try:
                    parsed_calls = json.loads(self.tool_calls)
                    if isinstance(parsed_calls, list):
                        valid_calls = []
                        for call in parsed_calls:
                            if isinstance(call, dict) and 'id' in call and 'type' in call and 'function' in call:
                                valid_calls.append(call)
                            else:
                                _logger.warning(f"OpenAI Format Msg {self.id}: Invalid tool call structure skipped: {call}")
                        if valid_calls:
                            api_tool_calls = valid_calls
                except json.JSONDecodeError:
                    _logger.warning(f"OpenAI Format Msg {self.id}: Failed to parse tool_calls JSON: {self.tool_calls}")

            if api_tool_calls:
                entry['tool_calls'] = api_tool_calls

            return entry

        elif tool_result_subtype and subtype_id == tool_result_subtype.id:
            if not self.tool_call_id or self.tool_call_result is None:
                _logger.warning(f"OpenAI Format: Skipping tool result message {self.id}: missing tool_call_id or result.")
                return None
            return {
                'role': 'tool',
                'tool_call_id': self.tool_call_id,
                'content': self.tool_call_result or ""
            }
        else:
            return None