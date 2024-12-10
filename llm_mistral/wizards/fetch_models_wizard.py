import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class FetchModelsWizard(models.TransientModel):
    _inherit = "llm.fetch.models.wizard"

    @api.model
    def _determine_model_use(self, name, capabilities):
        if any(cap in capabilities for cap in ["ocr"]):
            return "ocr"
        else:
            return super()._determine_model_use(name, capabilities)
