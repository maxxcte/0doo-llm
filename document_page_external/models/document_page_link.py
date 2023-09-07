import logging
import mimetypes
import requests

from odoo import fields, models, api
from odoo.tools import human_size

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

    @api.model_create_multi
    def create(self, vals_list):
        """Extend create to automatically retrieve MIME info for external links."""
        records = super().create(vals_list)

        # Process external links to retrieve MIME info
        external_links = records.filtered(lambda r: r.link_type == 'external' and not r.mime_type)
        for link in external_links:
            mime_info = self._get_link_mime_info(link.url)
            if mime_info.get('mime_type') or mime_info.get('content_size'):
                link.write(mime_info)

        return records

    @api.model
    def _get_link_mime_info(self, url):
        """Perform a HEAD request to get MIME type and content size."""
        result = {
            "mime_type": None,
            "content_size": None,
        }

        # Skip for non-http links
        if not url.startswith(('http://', 'https://', 'www.')):
            # Try to guess mime type from extension
            mime_type, _ = mimetypes.guess_type(url)
            if mime_type:
                result["mime_type"] = mime_type
            return result

        # Fix URLs starting with www.
        if url.startswith('www.'):
            url = 'http://' + url

        try:
            # Perform HEAD request with a timeout
            response = requests.head(url, timeout=5, allow_redirects=True)

            # Get content type from headers
            if 'Content-Type' in response.headers:
                content_type = response.headers['Content-Type']
                # Strip parameters like charset
                if ';' in content_type:
                    content_type = content_type.split(';')[0].strip()
                result["mime_type"] = content_type

            # Get content length if available
            if 'Content-Length' in response.headers:
                try:
                    size_bytes = int(response.headers['Content-Length'])
                    result["content_size"] = size_bytes // 1024  # Convert to KB
                except (ValueError, TypeError):
                    pass

        except requests.RequestException as e:
            _logger.warning("Failed to get MIME info for %s: %s", url, e)

        return result

    def open_link(self):
        """Action to open the link in a new browser tab."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_url",
            "url": self.url,
            "target": "new",
        }

    def refresh_mime_info(self):
        """Action to refresh MIME type and content size information."""
        for link in self.filtered(lambda r: r.link_type == 'external'):
            mime_info = self._get_link_mime_info(link.url)
            if mime_info.get('mime_type') or mime_info.get('content_size'):
                link.write(mime_info)
        return True
