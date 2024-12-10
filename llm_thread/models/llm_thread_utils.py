"""
Utility helper for LLM message construction and formatting.
"""

import emoji
import markdown2

from odoo.addons.llm_mail_message_subtypes.const import (
    LLM_ASSISTANT_SUBTYPE_XMLID,
    LLM_TOOL_RESULT_SUBTYPE_XMLID,
)


class LLMThreadUtils:
    @staticmethod
    def get_email_from(
        provider_name, provider_model_name, subtype_xmlid, author_id, tool_name=None
    ):
        if not author_id:
            if subtype_xmlid == LLM_TOOL_RESULT_SUBTYPE_XMLID:
                name = tool_name or "Tool"
                return f"{name} <tool@{provider_name.lower().replace(' ', '')}.ai>"
            elif subtype_xmlid == LLM_ASSISTANT_SUBTYPE_XMLID:
                model = provider_model_name or "Assistant"
                provider = provider_name.lower().replace(" ", "")
                return f"{model} <ai@{provider}.ai>"
        return None

    @staticmethod
    def build_post_vals(subtype_xmlid, body, author_id, email_from):
        return {
            "body": markdown2.markdown(emoji.demojize(body)),
            "message_type": "comment",
            "subtype_xmlid": subtype_xmlid,
            "author_id": author_id,
            "email_from": email_from or None,
            "partner_ids": [],
        }

    @staticmethod
    def build_update_vals(
        subtype_xmlid,
        tool_call_id=None,
        tool_calls=None,
        tool_call_definition=None,
        tool_call_result=None,
    ):
        if subtype_xmlid == LLM_ASSISTANT_SUBTYPE_XMLID and tool_calls:
            return {"tool_calls": tool_calls}
        if subtype_xmlid == LLM_TOOL_RESULT_SUBTYPE_XMLID:
            vals = {
                "tool_call_id": tool_call_id,
                "tool_call_definition": tool_call_definition,
                "tool_call_result": tool_call_result,
            }
            return {k: v for k, v in vals.items() if v is not None}
        return {}
