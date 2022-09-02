import logging

from odoo import models

_logger = logging.getLogger(__name__)


class LLMMailChannel(models.Model):
    _name = "llm.mail.channel"
    _description = "LLM Mail Channel"
    _inherit = ["mail.channel"]