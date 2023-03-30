import logging

from odoo import models

_logger = logging.getLogger(__name__)


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    def format_tools(self, tools):
        """Format tools for the specific provider"""
        return self._dispatch("format_tools", tools)

    def format_messages(self, messages):
        """Format messages for the specific provider
        
        Args:
            messages: mail.message recordset to format
            
        Returns:
            List of formatted messages in provider-specific format
        """
        return self._dispatch("format_messages", messages)
