# -*- coding: utf-8 -*-
import logging
from odoo import models, api

# Import constants from this module's const file
from ..const import (
    LLM_USER_SUBTYPE_XMLID,
    LLM_ASSISTANT_SUBTYPE_XMLID,
    LLM_TOOL_RESULT_SUBTYPE_XMLID,
)

_logger = logging.getLogger(__name__)

class MailMessageLLMSubtypes(models.Model):
    _inherit = 'mail.message'

    def _get_llm_message_format_fields(self):
        """
        Base method returns fields needed by this module for formatting.
        Inheriting modules (like llm_thread) MUST extend this list via super().
        """
        return ['subtype_id']

    @api.model
    def _get_llm_subtype_ids(self):
        """Helper to get the database IDs of the core LLM subtypes."""
        ids = set()
        try: ids.add(self.env['ir.model.data']._xmlid_to_res_id(LLM_USER_SUBTYPE_XMLID))
        except ValueError: _logger.error(f"XML ID not found: {LLM_USER_SUBTYPE_XMLID}")
        try: ids.add(self.env['ir.model.data']._xmlid_to_res_id(LLM_ASSISTANT_SUBTYPE_XMLID))
        except ValueError: _logger.error(f"XML ID not found: {LLM_ASSISTANT_SUBTYPE_XMLID}")
        try: ids.add(self.env['ir.model.data']._xmlid_to_res_id(LLM_TOOL_RESULT_SUBTYPE_XMLID))
        except ValueError: _logger.error(f"XML ID not found: {LLM_TOOL_RESULT_SUBTYPE_XMLID}")
        return ids


    def message_format(self, format_reply=True):
        """
        Base message_format override for LLM subtypes.
        Identifies LLM messages, adds common 'is_note' flag, and merges fields
        requested by _get_llm_message_format_fields (which llm_thread will extend).
        """
        vals_list = super().message_format(format_reply=format_reply)
        message_ids = [vals['id'] for vals in vals_list]
        if not message_ids:
            return vals_list

        llm_fields_to_fetch = list(set(self._get_llm_message_format_fields())) # Use set for uniqueness

        messages_data = {}
        if llm_fields_to_fetch:
             try:
                messages_data_list = self.env[self._name].sudo().search_read(
                    [('id', 'in', message_ids)],
                    llm_fields_to_fetch
                )
                messages_data = {msg['id']: msg for msg in messages_data_list}
             except Exception as e:
                 _logger.error(f"Error reading LLM fields for message_format: {e}. Fields requested: {llm_fields_to_fetch}")

        llm_subtype_ids = self._get_llm_subtype_ids()
        llm_subtype_xmlid_map = {
             self.env['ir.model.data']._xmlid_to_res_id(LLM_USER_SUBTYPE_XMLID): LLM_USER_SUBTYPE_XMLID,
             self.env['ir.model.data']._xmlid_to_res_id(LLM_ASSISTANT_SUBTYPE_XMLID): LLM_ASSISTANT_SUBTYPE_XMLID,
             self.env['ir.model.data']._xmlid_to_res_id(LLM_TOOL_RESULT_SUBTYPE_XMLID): LLM_TOOL_RESULT_SUBTYPE_XMLID,
        }

        for vals in vals_list:
            msg_data = messages_data.get(vals['id'], {})
            msg_subtype_id = vals.get('subtype_id')[0] if vals.get('subtype_id') else None

            if msg_subtype_id in llm_subtype_ids:
                vals['is_note'] = True
                vals['subtype_xmlid'] = llm_subtype_xmlid_map.get(msg_subtype_id)

                for field_name in llm_fields_to_fetch:
                    if field_name != 'subtype_id' and field_name in msg_data:
                        vals[field_name] = msg_data[field_name]
                    elif field_name != 'subtype_id' and field_name not in vals:
                        vals[field_name] = None

            else:
                vals['subtype_xmlid'] = None
                for field_name in llm_fields_to_fetch:
                    if field_name != 'subtype_id':
                        vals.pop(field_name, None)

        return vals_list