import logging

from pydantic import BaseModel, ConfigDict, Field

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolModelInspector(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("odoo_model_inspector", "Odoo Model Inspector")]

    def odoo_model_inspector_get_pydantic_model(self):
        class ModelInfoParams(BaseModel):
            """This function retrieves basic information about an Odoo model."""

            model_config = ConfigDict(
                title=self.name or "odoo_model_inspector",
            )
            model: str = Field(
                ...,
                description="The Odoo model name to get information about (example: res.partner)",
            )

        return ModelInfoParams

    def odoo_model_inspector_execute(self, parameters):
        """Execute the Odoo Model Inspector tool"""
        _logger.info(f"Executing Odoo Model Inspector with parameters: {parameters}")

        model_name = parameters.get("model")

        if not model_name:
            return {"error": "Model name is required"}

        try:
            # Search for the model in ir.model
            IrModel = self.env["ir.model"]
            model_info = IrModel.search_read(
                [("model", "=", model_name)], ["name", "model", "description"], limit=1
            )

            if not model_info:
                return {"error": f"Model '{model_name}' not found in ir.model"}

            # Get basic model information
            result = {
                "name": model_info[0]["name"],
                "model": model_info[0]["model"],
                "description": model_info[0]["description"] or "",
                "message": f"Model information retrieved successfully for {model_name}",
            }

            return result

        except Exception as e:
            _logger.exception(f"Error executing Odoo Model Inspector: {str(e)}")
            return {"error": str(e)}
