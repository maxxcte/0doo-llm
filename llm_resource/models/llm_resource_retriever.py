import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMResourceRetriever(models.Model):
    _inherit = "llm.resource"
    # Selection fields for retrievers and parsers
    retriever = fields.Selection(
        selection="_get_available_retrievers",
        string="Retriever",
        default="default",
        required=True,
        help="Method used to retrieve resource content",
        tracking=True,
    )

    @api.model
    def _get_available_retrievers(self):
        """Get all available retriever methods"""
        return [("default", "Default Retriever")]

    def retrieve(self):
        """Retrieve resource content from the related record with proper error handling and lock management"""
        resources_to_process = self.filtered(lambda d: d.state == "draft")
        if not resources_to_process:
            return False

        # Lock resources and process only the successfully locked ones
        resources = resources_to_process._lock()
        if not resources:
            return False

        # Track which resources have been processed successfully
        successful_resources = self.env["llm.resource"]

        try:
            # Process each resource
            for resource in resources:
                try:
                    # Get the related record
                    record = self.env[resource.res_model].browse(resource.res_id)
                    if not record.exists():
                        resource._post_message(
                            _("Referenced record not found"), "error"
                        )
                        continue

                    # Call the rag_retrieve method on the record if it exists
                    result = (
                        record.rag_retrieve(resource)
                        if hasattr(record, "rag_retrieve")
                        else None
                    )

                    # Mark as retrieved
                    resource.write(
                        {
                            "state": result.get("state", "retrieved")
                            if isinstance(result, dict)
                            else "retrieved"
                        }
                    )

                    # Track successful resource
                    successful_resources |= resource

                except Exception as e:
                    _logger.error(
                        "Error retrieving resource %s: %s",
                        resource.id,
                        str(e),
                        exc_info=True,
                    )
                    resource._post_message(
                        f"Error retrieving resource: {str(e)}", "error"
                    )

                    # Make sure to explicitly unlock the resource in case of error
                    resource._unlock()

            # Unlock all successfully processed resources
            successful_resources._unlock()
            return bool(successful_resources)

        except Exception as e:
            # Make sure to unlock ALL resources in case of a catastrophic error
            resources._unlock()
            _logger.error(
                "Critical error in batch retrieval: %s", str(e), exc_info=True
            )
            raise UserError(_("Error in batch retrieval: %s") % str(e)) from e
