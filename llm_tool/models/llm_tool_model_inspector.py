import logging
from typing import Any

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolModelInspector(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("odoo_model_inspector", "Odoo Model Inspector")]

    def odoo_model_inspector_execute(self, model: str) -> dict[str, Any]:
        """
        Retrieve basic information about an Odoo model

        Parameters:
            model: The Odoo model name to get information about (example: res.partner)
        """
        _logger.info(f"Executing Odoo Model Inspector with model: {model}")

        try:
            # Search for the model in ir.model
            IrModel = self.env["ir.model"]
            model_info = IrModel.search_read(
                [("model", "=", model)], ["name", "model"], limit=1
            )

            if not model_info:
                return {"error": f"Model '{model}' not found in ir.model"}

            # Get basic model information
            result = {
                "name": model_info[0]["name"],
                "model": model_info[0]["model"],
                "message": f"Model information retrieved successfully for {model}",
            }

            return result

        except Exception as e:
            _logger.exception(f"Error executing Odoo Model Inspector: {str(e)}")
            return {"error": str(e)}
