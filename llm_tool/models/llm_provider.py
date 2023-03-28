import logging

from odoo import models

_logger = logging.getLogger(__name__)


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    def format_tools_for_provider(self, tools):
        """Format tools for the specific provider"""
        return self._dispatch("format_tools", tools)
