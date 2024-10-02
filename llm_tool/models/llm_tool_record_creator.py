import logging
from typing import Any

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolRecordCreator(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("odoo_record_creator", "Odoo Record Creator")]

    def odoo_record_creator_execute(
        self, model: str, fields: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Create a new record in the specified Odoo model

        Parameters:
            model: The Odoo model to create a record in
            fields: Dictionary of field values for the new record
        """
        _logger.info(
            f"Executing Odoo Record Creator with: model={model}, fields={fields}"
        )

        model_obj = self.env[model]

        # Create the record
        new_record = model_obj.create(fields)

        # Return the ID and display name of the created record
        result = {
            "id": new_record.id,
            "display_name": new_record.display_name,
            "message": f"Record created successfully in {model}",
        }

        return result
