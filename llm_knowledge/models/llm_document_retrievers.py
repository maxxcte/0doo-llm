import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMDocumentRetriever(models.Model):
    _inherit = "llm.document"

    # Selection field for document retriever
    retriever = fields.Selection(
        selection="_get_available_retrievers",
        string="Retriever",
        default="default",
        required=True,
        help="Method used to retrieve document content",
        tracking=True,
    )

    @api.model
    def _get_available_retrievers(self):
        """Get all available retriever methods"""
        return [("default", "Default Retriever")]

    def retrieve(self):
        """Retrieve document content from the related record with proper error handling and lock management"""
        documents_to_process = self.filtered(lambda d: d.state == "draft")
        if not documents_to_process:
            return False

        # Lock documents and process only the successfully locked ones
        documents = documents_to_process._lock()
        if not documents:
            return False

        # Track which documents have been processed successfully
        successful_documents = self.env["llm.document"]

        try:
            # Process each document
            for document in documents:
                try:
                    # Get the related record
                    record = self.env[document.res_model].browse(document.res_id)
                    if not record.exists():
                        document._post_message(
                            _("Referenced record not found"), "error"
                        )
                        continue

                    # Call the rag_retrieve method on the record if it exists
                    result = (
                        record.rag_retrieve(document)
                        if hasattr(record, "rag_retrieve")
                        else None
                    )

                    # Mark as retrieved
                    document.write(
                        {
                            "state": result.get("state", "retrieved")
                            if isinstance(result, dict)
                            else "retrieved"
                        }
                    )

                    # Track successful document
                    successful_documents |= document

                except Exception as e:
                    _logger.error(
                        "Error retrieving document %s: %s",
                        document.id,
                        str(e),
                        exc_info=True,
                    )
                    document._post_message(
                        f"Error retrieving document: {str(e)}", "error"
                    )

                    # Make sure to explicitly unlock the document in case of error
                    document._unlock()

            # Unlock all successfully processed documents
            successful_documents._unlock()
            return bool(successful_documents)

        except Exception as e:
            # Make sure to unlock ALL documents in case of a catastrophic error
            documents._unlock()
            _logger.error(
                "Critical error in batch retrieval: %s", str(e), exc_info=True
            )
            raise UserError(_("Error in batch retrieval: %s") % str(e)) from e
