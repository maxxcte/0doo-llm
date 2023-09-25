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
        """Retrieve document content from the related record"""
        for document in self:
            if document.state != "draft":
                _logger.warning(
                    "Document %s must be in draft state to retrieve content",
                    document.id,
                )
                continue

        # Lock documents and process only the successfully locked ones
        documents = self._lock()
        if not documents:
            return False

        try:
            # Process each document
            for document in documents:
                try:
                    # Get the related record
                    record = self.env[document.res_model].browse(document.res_id)
                    if not record.exists():
                        raise UserError(_("Referenced record not found"))

                    # Call the rag_retrieve method on the record if it exists

                    result = record.rag_retrieve(document) if hasattr(record, "rag_retrieve") else None

                    # Mark as retrieved
                    document.write({"state": result.get("state", "retrieved") if isinstance(result, dict) else "retrieved"})

                except Exception as e:
                    document._post_message(
                        f"Error retrieving document: {str(e)}", "error"
                    )
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
            raise UserError(_("Error in batch retrieval: %s") % str(e)) from e
