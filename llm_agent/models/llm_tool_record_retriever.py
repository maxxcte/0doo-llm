import json
import logging

from pydantic import BaseModel, ConfigDict, Field

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolRecordRetriever(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("odoo_record_retriever", "Odoo Record Retriever")]

    def odoo_record_retriever_get_pydantic_model(self):
        # the docstring is used as default description for the tool
        class RecordRetrieverParams(BaseModel):
            """This function takes the parameters required for record retriever, including model, domain, fields, and limit."""

            model_config = ConfigDict(
                title=self.name or "odoo_record_retriever",
            )
            model: str = Field(
                ..., description="The Odoo model to retrieve records from"
            )
            domain: list = Field([], description="Domain to filter records")
            fields: list = Field([], description="Fields to retrieve")
            limit: int = Field(100, description="Maximum number of records to retrieve")

        return RecordRetrieverParams

    # Implementation of the Odoo Record Retriever tool
    def odoo_record_retriever_execute(self, parameters):
        """Execute the Odoo Record Retriever tool"""
        _logger.info(f"Executing Odoo Record Retriever with parameters: {parameters}")

        model_name = parameters.get("model")
        domain = parameters.get("domain", [])
        fields = parameters.get("fields", [])
        limit = parameters.get("limit", 100)

        if not model_name:
            return {"error": "Model name is required"}

        try:
            model = self.env[model_name]

            # Validate domain structure
            if not isinstance(domain, list):
                return {"error": "Domain must be a list of criteria"}

            # Using search_read for efficiency
            if fields:
                result = model.search_read(domain=domain, fields=fields, limit=limit)
            else:
                records = model.search(domain=domain, limit=limit)
                result = records.read()

            # Convert to serializable format
            return json.loads(json.dumps(result, default=str))

        except KeyError:
            return {"error": f"Model '{model_name}' not found"}
        except Exception as e:
            _logger.exception(f"Error executing Odoo Record Retriever: {str(e)}")
            return {"error": str(e)}
