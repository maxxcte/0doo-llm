import logging

from odoo import _, models

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def rag_parse(self, llm_resource):
        """
        Override the rag_parse method to handle PDFs if PyMuPDF is available
        """
        self.ensure_one()

        # Determine file type based on mimetype
        mimetype = self.mimetype or "application/octet-stream"

        # If it's a PDF and PyMuPDF is available, use PDF parser
        if mimetype == "application/pdf" and llm_resource.parser == "mistral_ocr":
            file_path = self._full_path(self.store_fname)
            _logger.info("File path: %s", file_path)
            llm_resource._parse_mistral_ocr(
                self.name,
                file_path,
            )
            
        return super().rag_parse(llm_resource)
