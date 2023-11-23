import logging

from typing import Any
from pydantic import BaseModel, ConfigDict, Field

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolRecordUnlinker(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("odoo_record_unlinker", "Odoo Record Unlinker")]

    def odoo_record_unlinker_get_pydantic_model(self):
        class RecordUnlinkerParams(BaseModel):
            """This function deletes records from the specified Odoo model based on the provided domain."""

            model_config = ConfigDict(
                title=self.name or "odoo_record_unlinker",
            )
            model: str = Field(..., description="The Odoo model to delete records from")
            domain: list[list[Any]] = Field(
                ..., description="Domain to identify records to delete"
            )
            limit: int = Field(
                1,
                description="Maximum number of records to delete (default: 1 for safety)",
            )

        return RecordUnlinkerParams

    def odoo_record_unlinker_execute(self, parameters):
        """Execute the Odoo Record Unlinker tool"""
        _logger.info(f"Executing Odoo Record Unlinker with parameters: {parameters}")

        model_name = parameters.get("model")
        domain = parameters.get("domain", [])
        limit = parameters.get("limit", 1)

        if not model_name:
            return {"error": "Model name is required"}

        if not domain:
            return {"error": "Domain is required to identify records to delete"}

        try:
            model = self.env[model_name]

            # Find records to delete
            records = model.search(domain, limit=limit)

            if not records:
                return {
                    "message": f"No records found matching the domain in {model_name}"
                }

            # Store record info before deletion for reporting
            record_info = [
                {"id": record.id, "display_name": record.display_name}
                for record in records
            ]

            # Count records to be deleted
            count = len(records)

            # Delete the records
            records.unlink()

            # Return information about the deleted records
            result = {
                "deleted_count": count,
                "deleted_records": record_info,
                "message": f"{count} record(s) deleted successfully from {model_name}",
            }

            return result

        except KeyError:
            return {"error": f"Model '{model_name}' not found"}
        except Exception as e:
            _logger.exception(f"Error executing Odoo Record Unlinker: {str(e)}")
            return {"error": str(e)}
