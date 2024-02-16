from odoo import api, fields, models
from odoo.exceptions import ValidationError


class MailMessage(models.Model):
    _inherit = "mail.message"

    llm_tool_calls = fields.Text(
        string="LLM Tool Calls",
        help="JSON serialized list of tool calls made by the assistant in this message.",
        readonly=True, copy=False)
    llm_tool_call_id = fields.Char(
        string="LLM Tool Call ID",
        help="The unique ID of the tool call this message is a result for.",
        readonly=True, index=True, copy=False)
    # Definition might be useful for displaying the request directly on the tool message
    llm_tool_call_definition = fields.Text(
        string="LLM Tool Call Definition",
        help="JSON serialized definition of the tool call (type, function name, arguments). Copied from the request.",
        readonly=True, copy=False
    )
    llm_tool_call_result = fields.Text(
        string="LLM Tool Call Result",
        help="JSON serialized result returned by the tool execution (or error).",
        readonly=True, copy=False)


    @api.constrains("llm_tool_call_id", "subtype_id")
    def _check_tool_message_integrity(self):
        for record in self:
            if record.llm_tool_call_id and record.subtype_id:
                tool_message_subtype = self.env.ref("llm_tool.mt_tool_message")
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
            'llm_tool_calls', 'llm_tool_call_id', 'llm_tool_call_definition',
            'llm_tool_call_result', 'user_vote', 'subtype_id'
        ]
        messages_data = self.env[self._name].sudo().search_read(
            [('id', 'in', message_ids)], llm_fields
        )
        messages_data_map = {msg['id']: msg for msg in messages_data}


        mt_llm_user_id = self.env['ir.model.data']._xmlid_to_res_id('llm_thread.mt_llm_user')
        mt_llm_assistant_id = self.env['ir.model.data']._xmlid_to_res_id('llm_thread.mt_llm_assistant')
        mt_llm_tool_result_id = self.env['ir.model.data']._xmlid_to_res_id('llm_thread.mt_llm_tool_result')

        for vals in vals_list:
            msg_data = messages_data_map.get(vals['id'], {})

            vals['llm_tool_calls'] = msg_data.get('llm_tool_calls')
            vals['llm_tool_call_id'] = msg_data.get('llm_tool_call_id')
            vals['llm_tool_call_definition'] = msg_data.get('llm_tool_call_definition')
            vals['llm_tool_call_result'] = msg_data.get('llm_tool_call_result')
            
            if msg_data.get('subtype_id') in [mt_llm_user_id, mt_llm_assistant_id, mt_llm_tool_result_id]:
                # is_note is important for Message component to render with bubble
                vals['is_note'] = True
                if msg_data.get('subtype_id') == mt_llm_user_id:
                    vals['subtype_xmlid'] = 'llm_thread.mt_llm_user'
                elif msg_data.get('subtype_id') == mt_llm_assistant_id:
                    vals['subtype_xmlid'] = 'llm_thread.mt_llm_assistant'
                elif msg_data.get('subtype_id') == mt_llm_tool_result_id:
                    vals['subtype_xmlid'] = 'llm_thread.mt_llm_tool_result'
            else:
                vals['subtype_xmlid'] = None

        return vals_list
