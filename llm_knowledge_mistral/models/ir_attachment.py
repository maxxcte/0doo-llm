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