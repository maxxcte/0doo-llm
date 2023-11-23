import logging

from pydantic import BaseModel, ConfigDict, Field

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolFieldsInspector(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("odoo_fields_inspector", "Odoo Fields Inspector")]

    def odoo_fields_inspector_get_pydantic_model(self):
        class ModelFieldsParams(BaseModel):
            """This function retrieves detailed field information for an Odoo model."""

            model_config = ConfigDict(
                title=self.name or "odoo_fields_inspector",
            )
            model: str = Field(
                ...,
                description="The Odoo model name to get field information for (example: res.partner)",
            )
            field_names: list[str] = Field(
                default=None,
                description="Optional list of specific field names to retrieve (if empty, all fields will be returned)",
            )
            limit: int = Field(
                default=0,
                description="Maximum number of fields to return (0 means no limit). Can be useful as some odoo models have massive amount of fields",
            )

        return ModelFieldsParams

    def odoo_fields_inspector_execute(self, parameters):
        """Execute the Odoo Fields Inspector tool"""
        _logger.info(f"Executing Odoo Fields Inspector with parameters: {parameters}")

        model_name = parameters.get("model")
        field_names = parameters.get("field_names", None)
        limit = parameters.get("limit", 0)

        if not model_name:
            return {"error": "Model name is required"}

        try:
            # Check if model exists
            if model_name not in self.env:
                return {"error": f"Model '{model_name}' not found"}

            model = self.env[model_name]

            # Get field information using fields_get method
            if field_names:
                fields_info = model.fields_get(field_names)
            else:
                fields_info = model.fields_get()

            # Process field information to make it more readable
            processed_fields = {}
            total_fields = len(fields_info)

            # Apply limit if specified
            if limit > 0:
                # Convert to list of items, slice, then convert back to dict
                field_items = list(fields_info.items())[:limit]
                fields_info = dict(field_items)

            for field_name, field_data in fields_info.items():
                processed_field = {
                    "name": field_name,
                    "type": field_data.get("type"),
                    "string": field_data.get("string"),
                    "help": field_data.get("help", ""),
                    "required": field_data.get("required", False),
                    "readonly": field_data.get("readonly", False),
                    "store": field_data.get("store", True),
                }

                # Add relation info if it's a relational field
                if field_data.get("relation"):
                    processed_field["relation"] = field_data.get("relation")
                    processed_field["relation_field"] = field_data.get(
                        "relation_field", ""
                    )

                # Add selection values if it's a selection field
                if field_data.get("selection"):
                    # Convert selection to dict for easier consumption
                    if isinstance(field_data.get("selection"), list):
                        selection_dict = {
                            key: value for key, value in field_data.get("selection", [])
                        }
                        processed_field["selection"] = selection_dict

                processed_fields[field_name] = processed_field

            result = {
                "model": model_name,
                "fields": processed_fields,
                "field_count": len(processed_fields),
                "total_fields": total_fields,
                "limited": limit > 0 and total_fields > limit,
                "message": f"Field information retrieved successfully for {model_name}"
                + (
                    f" (limited to {limit} fields)"
                    if limit > 0 and total_fields > limit
                    else ""
                ),
            }

            return result

        except Exception as e:
            _logger.exception(f"Error executing Odoo Fields Inspector: {str(e)}")
            return {"error": str(e)}
