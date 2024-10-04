import logging

from odoo import _, api, models, fields

_logger = logging.getLogger(__name__)


class LLMResourceParser(models.Model):
    _inherit = "llm.resource"

    llm_model_id = fields.Many2one(
        "llm.model",
        string="Model",
        required=False,
        domain="[('model_use', 'in', ['ocr'])]",
        ondelete="restrict",
    )

    llm_provider_id = fields.Many2one(
        "llm.provider",
        string="Provider",
        domain="[('service', '=', 'mistral')]",
        required=False,
        ondelete="restrict",
    )

    @api.model
    def _get_available_parsers(self):
        parsers = super()._get_available_parsers()
        parsers.extend(
            [
                ("mistral_ocr", "Mistral OCR Parser"),
            ]
        )
        return parsers

    def _parse_mistral_ocr(self, resource):
        """
        Parse the resource content using Mistral OCR.
        """
        try:
            # TODO: Implement Mistral OCR parsing
            return True
        except Exception as e:
            _logger.error("Error parsing resource %s: %s", resource.id, str(e))
            return False