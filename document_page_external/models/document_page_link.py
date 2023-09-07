# models/document_page_link.py
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
    mime_type_updated = fields.Boolean(
        string="MIME Type Updated",
        default=False,
        help="Indicates if MIME type has been updated",
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
        """Create links without fetching MIME types immediately."""
        # Basic MIME type guessing for file extensions
        for vals in vals_list:
            url = vals.get('url', '')
            # Only try to guess MIME type for non-HTTP urls
            if url and not url.startswith(('http://', 'https://', 'www.')):
                mime_type, _ = mimetypes.guess_type(url)
                if mime_type:
                    vals['mime_type'] = mime_type
                    vals['mime_type_updated'] = True

        return super().create(vals_list)

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
                link.write({
                    'mime_type': mime_info.get('mime_type'),
                    'content_size': mime_info.get('content_size'),
                    'mime_type_updated': True,
                })
        return True

    @api.model
    def update_pending_mime_types(self, limit=50):
        """Update MIME types for links that haven't been processed yet.
        This can be called from a scheduled action."""
        links = self.search([
            ('link_type', '=', 'external'),
            ('mime_type_updated', '=', False)
        ], limit=limit)

        for link in links:
            try:
                mime_info = self._get_link_mime_info(link.url)
                update_vals = {'mime_type_updated': True}

                if mime_info.get('mime_type'):
                    update_vals['mime_type'] = mime_info['mime_type']
                if mime_info.get('content_size'):
                    update_vals['content_size'] = mime_info['content_size']

                link.write(update_vals)

                # Small delay to avoid overwhelming external servers
                import time
                time.sleep(0.1)

            except Exception as e:
                _logger.error("Error updating MIME info for link %s: %s", link.id, e)
                # Mark as updated anyway to avoid retrying forever
                link.write({'mime_type_updated': True})

        return True
