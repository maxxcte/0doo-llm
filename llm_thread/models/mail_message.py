# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api
from odoo.exceptions import ValidationError

from .const import (
    LLM_TOOL_RESULT_SUBTYPE_XMLID,
    LLM_USER_SUBTYPE_XMLID,
    LLM_ASSISTANT_SUBTYPE_XMLID,
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
    
    def message_format(self, format_reply=True):
        """
        Override message_format to ensure LLM-specific fields and subtype info
        are available for frontend processing and rendering.
        """
        # Get the standard formatted values first
        vals_list = super().message_format(format_reply=format_reply)

        message_ids = [vals['id'] for vals in vals_list]
        if not message_ids:
            return vals_list

        # Efficiently fetch LLM fields and subtype info for the messages being formatted
        llm_fields = [
            'tool_calls', 'tool_call_id', 'tool_call_definition',
            'tool_call_result', 'user_vote', 'subtype_id', 'user_vote'
        ]
        messages_data = self.env[self._name].sudo().search_read(
            [('id', 'in', message_ids)], llm_fields
        )
        messages_data_map = {msg['id']: msg for msg in messages_data}

        mt_llm_user_id = self.env['ir.model.data']._xmlid_to_res_id(LLM_USER_SUBTYPE_XMLID)
        mt_llm_assistant_id = self.env['ir.model.data']._xmlid_to_res_id(LLM_ASSISTANT_SUBTYPE_XMLID)
        mt_llm_tool_result_id = self.env['ir.model.data']._xmlid_to_res_id(LLM_TOOL_RESULT_SUBTYPE_XMLID)

        for vals in vals_list:
            msg_data = messages_data_map.get(vals['id'], {})

            vals['tool_calls'] = msg_data.get('tool_calls')
            vals['tool_call_id'] = msg_data.get('tool_call_id')
            vals['tool_call_definition'] = msg_data.get('tool_call_definition')
            vals['tool_call_result'] = msg_data.get('tool_call_result')
            vals['user_vote'] = msg_data.get('user_vote')
            
            if msg_data.get('subtype_id') in [mt_llm_user_id, mt_llm_assistant_id, mt_llm_tool_result_id]:
                # is_note is important for Message component to render with bubble
                vals['is_note'] = True
                if msg_data.get('subtype_id') == mt_llm_user_id:
                    vals['subtype_xmlid'] = LLM_USER_SUBTYPE_XMLID
                elif msg_data.get('subtype_id') == mt_llm_assistant_id:
                    vals['subtype_xmlid'] = LLM_ASSISTANT_SUBTYPE_XMLID
                elif msg_data.get('subtype_id') == mt_llm_tool_result_id:
                    vals['subtype_xmlid'] = LLM_TOOL_RESULT_SUBTYPE_XMLID
            else:
                vals['subtype_xmlid'] = None

        return vals_list
