
import json

from odoo import fields, models, api
from odoo.exceptions import ValidationError, MissingError, UserError


class LLMTool(models.Model):
    _inherit = "llm.tool"
    _description = "LLM Tool"

    @staticmethod
    def create_tool_response_from_signature(tool_name, arguments_str, tool_call_id, result_data):
        """Create a standardized tool response structure."""
        return {
            "id": tool_call_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": arguments_str,
            },
            "result": json.dumps(result_data),
        }