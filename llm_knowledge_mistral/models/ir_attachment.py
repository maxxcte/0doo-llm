import logging

from odoo import models

_logger = logging.getLogger(__name__)


# Mimetypes supported by Mistral OCR (Adjust as needed based on Mistral's capabilities)
# Also this can be configurable I believe?
MISTRAL_OCR_SUPPORTED_MIMETYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/tiff",
}


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def rag_parse(self, llm_resource):
        """
        Override the rag_parse method to handle PDFs if Mistral OCR is selected
        """
        self.ensure_one()

        # Determine file type based on mimetype
        mimetype = self.mimetype or "application/octet-stream"

        # If it's a supported mimetype and Mistral OCR is selected, use Mistral OCR parser
        if (
            mimetype in MISTRAL_OCR_SUPPORTED_MIMETYPES
            and llm_resource.parser == "mistral_ocr"
        ):
            file_path = self._full_path(self.store_fname)
            return llm_resource._parse_mistral_ocr(
                self.name,
                file_path,
                mimetype,
            )

        return super().rag_parse(llm_resource)
