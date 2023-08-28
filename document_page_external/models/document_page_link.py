import logging
import mimetypes

from odoo import fields, models

_logger = logging.getLogger(__name__)


class DocumentPageLink(models.Model):
    """Store links extracted from document pages."""

    _name = "document.page.link"
    _description = "Document Page Link"
    _order = "create_date desc"

    name = fields.Char(
        string="Title",
        help="Link title or description",
    )
    url = fields.Char(
        string="URL",
        required=True,
        help="The URL of the link",
        index=True,
    )
    page_id = fields.Many2one(
        comodel_name="document.page",
        string="Document Page",
        required=True,
        ondelete="cascade",
        index=True,
    )
    link_type = fields.Selection(
        [
            ("internal", "Internal Link"),
            ("external", "External Link"),
            ("mailto", "Email Link"),
            ("other", "Other"),
        ],
        string="Link Type",
        default="external",
        required=True,
    )
    mime_type = fields.Char(
        string="MIME Type",
        help="Content type of the linked resource",
        index=True,
    )
    content_size = fields.Integer(
        string="Size (KB)",
        help="Size of the linked resource in kilobytes",
    )
    active = fields.Boolean(default=True)

    _sql_constraints = [
        (
            "url_page_uniq",
            "unique(url, page_id)",
            "This URL already exists for this document page!",
        ),
    ]

    def open_link(self):
        """Action to open the link in a new browser tab."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.url,
            "target": "new",
        }