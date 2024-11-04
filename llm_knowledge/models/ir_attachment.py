import logging

from odoo import models

_logger = logging.getLogger(__name__)

try:
    import pymupdf
except ImportError:
    pymupdf = None


class IrAttachmentPDFExtension(models.Model):
    _inherit = "ir.attachment"
