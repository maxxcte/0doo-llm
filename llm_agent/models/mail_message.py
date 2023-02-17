from odoo import fields, models, api
from odoo.exceptions import ValidationError
import json

class MailMessage(models.Model):
    _inherit = "mail.message"

    tool_call_id = fields.Char(
        string="Tool Call ID",
        help="Identifier of the tool call that generated this message",
    )
    
    tool_calls = fields.Text(
        string="Tool Calls",
        help="JSON representation of tool calls made by the assistant",
    )

    @api.constrains("tool_call_id", "subtype_id")
    def _check_tool_message_integrity(self):
        for record in self:
            if record.tool_call_id and record.subtype_id:
                tool_message_subtype = self.env.ref("llm_agent.mt_tool_message")
                if record.subtype_id.id != tool_message_subtype.id:
                    raise ValidationError("Tool Call ID can only be set for Tool Messages.")

    def to_provider_message(self):
        """Override to_provider_message to support tool messages and assistant messages with tool calls"""
        # Check if this is a tool message
        if self.subtype_id and self.tool_call_id:
            tool_message_subtype = self.env.ref("llm_agent.mt_tool_message")
            if self.subtype_id.id == tool_message_subtype.id:
                return {
                    "role": "tool",
                    "tool_call_id": self.tool_call_id,
                    "content": self.body,
                }
        
        # Check if this is an assistant message with tool calls
        if not self.author_id and self.tool_calls:
            try:
                tool_calls_data = json.loads(self.tool_calls)
                return {
                    "role": "assistant",
                    "content": self.body or None,
                    "tool_calls": tool_calls_data,
                }
            except (json.JSONDecodeError, ValueError):
                # If JSON parsing fails, fall back to default behavior
                pass
        
        # Default behavior from parent
        return super(MailMessage, self).to_provider_message()