import json
import logging

from odoo import models, tools
from ..utils.tool_id_utils import ToolIdUtils
_logger = logging.getLogger(__name__)


class MailMessage(models.Model):
    _inherit = "mail.message"

    def ollama_format_message(self):
        """Provider-specific formatting for Ollama."""
        self.ensure_one()
        body = self.body
        if body:
            body = tools.html2plaintext(body)

        if self.is_llm_user_message():
            formatted_message = {'role': 'user'}
            if body:
                formatted_message['content'] = body
            return formatted_message

        elif self.is_llm_assistant_message():
            formatted_message = {'role': 'assistant'}
            content = tools.html2plaintext(self.body) if self.body else ""
            if content:
                formatted_message['content'] = content

            if self.tool_calls:
                try:
                    parsed_calls = json.loads(self.tool_calls)
                    if isinstance(parsed_calls, list):
                        for call in parsed_calls:
                            function_details = call.get('function', {})
                            if isinstance(function_details, dict):
                                arguments = function_details.get('arguments')
                                if isinstance(arguments, str):
                                    try:
                                        function_details['arguments'] = json.loads(arguments)
                                    except json.JSONDecodeError:
                                        _logger.warning(
                                            f"Ollama Format Msg {self.id}: Failed to parse arguments JSON string for tool call {call.get('id')}: {arguments}. Replacing with empty dict."
                                        )
                                        function_details['arguments'] = {}
                        formatted_message['tool_calls'] = parsed_calls
                    else:
                        _logger.info(f"Ollama Format Msg {self.id}: Parsed tool_calls is not a list: {parsed_calls}")
                except json.JSONDecodeError:
                    _logger.info(f"Ollama Format Msg {self.id}: Failed to parse tool_calls JSON: {self.tool_calls}")

            return formatted_message

        elif self.is_llm_tool_result_message():
            if not self.tool_call_id or self.tool_call_result is None:
                _logger.warning(f"Ollama Format: Skipping tool result message {self.id}: missing tool_call_id or result.")
                return None
            tool_name = ToolIdUtils.extract_tool_name_from_id(self.tool_call_id)
            formatted_message = {'role': 'tool', 'name': tool_name, 'content': self.tool_call_result}
            return formatted_message
        else:
            return None