import logging
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolRecordUpdater(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("odoo_record_updater", "Odoo Record Updater")]

    def odoo_record_updater_get_pydantic_model(self):
        class RecordUpdaterParams(BaseModel):
            """This function updates existing records in the specified Odoo model that match the given domain with the provided values."""

            model_config = ConfigDict(
                title=self.name or "odoo_record_updater",
            )
            model: str = Field(..., description="The Odoo model to update records in")
            domain: list[list[Any]] = Field(
                ..., description="Domain to identify records to update"
            )
            values: dict = Field(
                ..., description="Dictionary of field values to update"
            )
            limit: int = Field(
                1,
                description="Maximum number of records to update (default: 1 for safety)",
            )

        return RecordUpdaterParams

    def odoo_record_updater_execute(self, parameters):
        """Execute the Odoo Record Updater tool"""
        _logger.info(f"Executing Odoo Record Updater with parameters: {parameters}")

        model_name = parameters.get("model")
        domain = parameters.get("domain", [])
        values = parameters.get("values", {})
        limit = parameters.get("limit", 1)  # Default to 1 for safety

        if not model_name:
            return {"error": "Model name is required"}

        if not domain:
            return {"error": "Domain is required to identify records to update"}

        if not values:
            return {"error": "Values dictionary is required"}

        try:
            model = self.env[model_name]

            # Validate domain structure
            if not isinstance(domain, list):
                return {"error": "Domain must be a list of criteria"}

            # Find records to update
            records = model.search(domain, limit=limit)

            if not records:
                return {"error": "No records found matching the domain"}

            # Update the records
            records.write(values)

            # Return information about updated records
            result = {
                "count": len(records),
                "ids": records.ids,
                "message": f"Successfully updated {len(records)} record(s) in {model_name}",
            }

            return result

        except KeyError:
            return {"error": f"Model '{model_name}' not found"}
        except Exception as e:
            _logger.exception(f"Error executing Odoo Record Updater: {str(e)}")
            return {"error": str(e)}
