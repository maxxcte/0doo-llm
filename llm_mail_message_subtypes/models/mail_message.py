import logging
from odoo import models, api

from ..const import (
    LLM_USER_SUBTYPE_XMLID,
    LLM_ASSISTANT_SUBTYPE_XMLID,
    LLM_TOOL_RESULT_SUBTYPE_XMLID,
)

_logger = logging.getLogger(__name__)

class MailMessageLLMSubtypes(models.Model):
    _inherit = 'mail.message'

    def _get_llm_message_format_fields(self):
        """Returns fields needed by this module for formatting for frontend."""
        return ['subtype_id']

    @api.model
    def _get_llm_subtype_data(self):
        """
        Helper to get the database IDs and XML IDs of the core LLM subtypes.
        Returns:
            tuple: (set_of_llm_subtype_ids, dict_mapping_id_to_xmlid)
        """
        ids = set()
        id_to_xmlid = {}
        subtype_xml_ids = [
            LLM_USER_SUBTYPE_XMLID,
            LLM_ASSISTANT_SUBTYPE_XMLID,
            LLM_TOOL_RESULT_SUBTYPE_XMLID,
        ]
        for xmlid in subtype_xml_ids:
            res_id = self.env['ir.model.data']._xmlid_to_res_id(xmlid, raise_if_not_found=True)
            if isinstance(res_id, int):
                ids.add(res_id)
                id_to_xmlid[res_id] = xmlid

        return ids, id_to_xmlid


    def message_format(self, format_reply=True):
        """
        Base message_format override for LLM subtypes. (Optimized)
        """
        vals_list = super().message_format(format_reply=format_reply)
        message_ids = [vals['id'] for vals in vals_list]
        if not message_ids:
            return vals_list

        llm_fields_to_fetch = list(set(self._get_llm_message_format_fields()))
        messages_data = {}
        if llm_fields_to_fetch:
            messages_data_list = self.browse(message_ids).sudo().read(llm_fields_to_fetch)
            messages_data = {msg['id']: msg for msg in messages_data_list}

        llm_subtype_ids, llm_id_to_xmlid_map = self._get_llm_subtype_data()

        for vals in vals_list:
            msg_data = messages_data.get(vals['id'], {})
            msg_subtype_id = vals.get('subtype_id')[0] if vals.get('subtype_id') else None

            if msg_subtype_id in llm_subtype_ids:
                # Render using note style for custom llm subtypes
                vals['is_note'] = True
                vals['subtype_xmlid'] = llm_id_to_xmlid_map.get(msg_subtype_id)

                for field_name in llm_fields_to_fetch:
                    if field_name != 'subtype_id' and field_name in msg_data:
                        vals[field_name] = msg_data[field_name]
                    elif field_name != 'subtype_id' and field_name not in vals:
                        vals[field_name] = None
            else:
                vals['subtype_xmlid'] = None

        return vals_list
    
    def is_llm_user_message(self):
        return self.subtype_id == self.env.ref(LLM_USER_SUBTYPE_XMLID)
    
    def is_llm_assistant_message(self):
        return self.subtype_id == self.env.ref(LLM_ASSISTANT_SUBTYPE_XMLID)
    
    def is_llm_tool_result_message(self):
        return self.subtype_id == self.env.ref(LLM_TOOL_RESULT_SUBTYPE_XMLID)