import json
import logging

from pydantic import BaseModel, ConfigDict, Field

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolRecordCreator(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("odoo_record_creator", "Odoo Record Creator")]

    def odoo_record_creator_get_pydantic_model(self):
        class RecordCreatorParams(BaseModel):
            """This function creates a new record in the specified Odoo model with the provided values."""

            model_config = ConfigDict(
                title=self.name or "odoo_record_creator",
            )
            model: str = Field(
                ..., description="The Odoo model to create a record in"
            )
            values: dict = Field(
                ..., description="Dictionary of field values for the new record"
            )

        return RecordCreatorParams

    def odoo_record_creator_execute(self, parameters):
        """Execute the Odoo Record Creator tool"""
        _logger.info(f"Executing Odoo Record Creator with parameters: {parameters}")

        model_name = parameters.get("model")
        values = parameters.get("values", {})

        if not model_name:
            return {"error": "Model name is required"}
        
        if not values:
            return {"error": "Values dictionary is required"}

        try:
            model = self.env[model_name]
            
            # Create the record
            new_record = model.create(values)
            
            # Return the ID and display name of the created record
            result = {
                "id": new_record.id,
                "display_name": new_record.display_name,
                "message": f"Record created successfully in {model_name}"
            }
            
            return result

        except KeyError:
            return {"error": f"Model '{model_name}' not found"}
        except Exception as e:
            _logger.exception(f"Error executing Odoo Record Creator: {str(e)}")
            return {"error": str(e)}