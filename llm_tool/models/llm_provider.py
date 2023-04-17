import logging

from odoo import models, api

_logger = logging.getLogger(__name__)


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    def format_tools(self, tools):
        """Format tools for the specific provider"""
        return self._dispatch("format_tools", tools)
    
    def format_messages(self, messages):
        """Format messages for this provider

        Args:
            messages: mail.message recordset to format

        Returns:
            List of formatted messages in provider-specific format
        """
        return self._dispatch("format_messages", messages)

    @api.model
    def _default_format_message(self, message):
        """Default implementation for formatting message

        This provides a basic implementation that can be overridden by provider-specific modules.

        Args:
            message: mail.message record to format

        Returns:
            Formatted message in a standard format
        """

        return {
            "role": "user" if message.author_id else "assistant",
            "content": message.body or "",  # Ensure content is never null
        }