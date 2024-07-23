import json

from odoo import models, api
import logging

_logger = logging.getLogger(__name__)

class LLMProvider(models.Model):
    _inherit = "llm.provider"

    @api.model
    def _is_tool_call_complete(self, function_data, expected_endings=(']', '}')):
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