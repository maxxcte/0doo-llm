from odoo import api, fields, models
from odoo.exceptions import ValidationError


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
                tool_message_subtype = self.env.ref("llm_tool.mt_tool_message")
                if record.subtype_id.id != tool_message_subtype.id:
                    raise ValidationError(
                        "Tool Call ID can only be set for Tool Messages."
                    )

    def message_format(self, format_reply=True):
        """Override message_format to mark tool messages as notes for proper UI rendering"""
        vals_list = super().message_format(format_reply=format_reply)

        # Get the tool message subtype ID
        tool_message_id = self.env.ref("llm_tool.mt_tool_message").id

        # Update is_note for tool messages
        for vals in vals_list:
            message_sudo = self.browse(vals["id"]).sudo().with_prefetch(self.ids)
            if message_sudo.subtype_id.id == tool_message_id:
                vals["is_note"] = True
                vals["is_tool_message"] = True
            else:
                vals["is_tool_message"] = False

        return vals_list
