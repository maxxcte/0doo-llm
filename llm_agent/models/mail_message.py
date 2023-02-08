from odoo import fields, models, api
from odoo.exceptions import ValidationError
class MailMessage(models.Model):
    _inherit = "mail.message"

    tool_call_id = fields.Char(
        string="Tool Call ID",
        help="Identifier of the tool call that generated this message",
    )

    @api.constrains("tool_call_id", "subtype_id")
    def _check_tool_message_integrity(self):
        for record in self:
            if record.tool_call_id and record.subtype_id.xml_id != "llm_agent.mt_tool_message":
                raise ValidationError("Tool Call ID can only be set for Tool Messages.")