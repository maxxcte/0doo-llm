# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.exceptions import ValidationError

from odoo.addons.llm_mail_message_subtypes.const import (
    LLM_TOOL_RESULT_SUBTYPE_XMLID,
)

class MailMessage(models.Model):
    _inherit = "mail.message"

    user_vote = fields.Integer(
        string="User Vote",
        default=0,
        help="Vote status given by the user. 0: No vote, 1: Upvoted, -1: Downvoted.",
    )

    @api.constrains("tool_call_id", "subtype_id")
    def _check_tool_message_integrity(self):
        for record in self:
            if record.tool_call_id and record.subtype_id:
                tool_message_subtype = self.env.ref(LLM_TOOL_RESULT_SUBTYPE_XMLID)
                if record.subtype_id.id != tool_message_subtype.id:
                    raise ValidationError(
                        "Tool Call ID can only be set for Tool Messages."
                    )
    
    def _get_llm_message_format_fields(self):
        """Extend the list of fields fetched by the base message_format."""
        fields_list = super()._get_llm_message_format_fields()
        fields_list.extend([
            'tool_calls',
            'tool_call_id',
            'tool_call_definition',
            'tool_call_result',
            'user_vote',
        ])
        return fields_list