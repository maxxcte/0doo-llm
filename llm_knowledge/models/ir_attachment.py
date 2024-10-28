import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import pymupdf
except ImportError:
    pymupdf = None


class IrAttachmentPDFExtension(models.Model):
    _inherit = "ir.attachment"

    def rag_parse(self, llm_resource):
        """
        Override the rag_parse method to handle PDFs if PyMuPDF is available
        """
        self.ensure_one()

        # Determine file type based on mimetype
        mimetype = self.mimetype or "application/octet-stream"

        # If it's a PDF and PyMuPDF is available, use PDF parser
        if mimetype == "application/pdf" and pymupdf:
            return self._parse_pdf(llm_resource)
        else:
            # Otherwise fall back to the base implementation
            return super().rag_parse(llm_resource)
