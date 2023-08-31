import logging
import re
import mimetypes

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.tools import human_size

_logger = logging.getLogger(__name__)


class DocumentPage(models.Model):
    """Extend document.page model with external URL functionality."""

    _inherit = "document.page"

    external_url = fields.Char(
        string="External URL",
        help="URL of external content to fetch",
    )

    link_ids = fields.One2many(
        comodel_name="document.page.link",
        inverse_name="page_id",
        string="Links",
        help="Links extracted from the document content",
    )

    link_count = fields.Integer(
        string="Links Count",
        compute="_compute_link_count",
        store=False,
    )

    def _compute_link_count(self):
        """Compute the number of links for each page."""
        for page in self:
            page.link_count = len(page.link_ids)

    def action_retrieve_content(self):
        """Directly retrieve content from the external URL."""
        self.ensure_one()
        if not self.external_url:
            raise UserError(_("Please set an external URL first."))

        summary = _("Retrieved from external URL: %s") % self.external_url
        return self.retrieve_from_external_url(summary)

    def get_link_mime_info(self, url):
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

    def extract_links_from_content(self, content):
        """Extract links from HTML content and create document.page.link records."""
        self.ensure_one()

        # Simple regex to extract links from HTML content
        # This could be improved with BeautifulSoup if installed
        links = []

        # Extract <a href="..."> links
        href_pattern = re.compile(r'<a\s+(?:[^>]*?\s+)?href="([^"]*)"(?:\s+[^>]*?)?(?:\s*>\s*(.*?)\s*</a>)', re.IGNORECASE | re.DOTALL)
        for match in href_pattern.finditer(content):
            url = match.group(1)
            title = re.sub(r'<[^>]*>', '', match.group(2) or '').strip() or url

            # Determine link type
            link_type = "external"
            if url.startswith("mailto:"):
                link_type = "mailto"
            elif url.startswith("/") or url.startswith("#") or (not url.startswith("http") and not url.startswith("www")):
                link_type = "internal"

            links.append({
                "url": url,
                "name": title,
                "link_type": link_type,
            })

        # Create document.page.link records
        existing_urls = set(self.link_ids.mapped('url'))
        for link_data in links:
            if link_data['url'] not in existing_urls:
                # Get MIME type and size information for external links
                if link_data['link_type'] == 'external':
                    mime_info = self.get_link_mime_info(link_data['url'])
                    link_data.update(mime_info)

                self.env['document.page.link'].create({
                    'page_id': self.id,
                    **link_data,
                })

        return True

    def retrieve_from_external_url(self, summary=None):
        """Fetch content from external URL and create history entry."""
        self.ensure_one()
        if not self.external_url:
            raise UserError(_("No external URL set for this page."))

        try:
            response = requests.get(self.external_url, timeout=10)
            response.raise_for_status()
            content = response.text

            # For draft records, populate the name and content directly
            if not self.name:
                # Extract title from content if possible (simple HTML title extraction)
                import re

                title_match = re.search(r"<title>(.*?)</title>", content, re.IGNORECASE)
                if title_match:
                    self.name = title_match.group(1)
                else:
                    self.name = "Content from " + self.external_url

            # Create a history entry with the new content
            history_vals = {
                "page_id": self.id,
                "name": self.draft_name or "1.0",
                "summary": summary
                           or _("Retrieved from external URL: %s") % self.external_url,
                "content": content,
            }
            self._create_history(history_vals)

            # Extract and store links
            self.extract_links_from_content(content)

            return True
        except requests.RequestException as e:
            _logger.error("Error fetching content from %s: %s", self.external_url, e)
            raise UserError(
                _("Failed to retrieve content from URL: %s") % str(e)
            ) from e

    def action_view_links(self):
        """Action to view the links associated with this page."""
        self.ensure_one()
        return {
            "name": _("Links"),
            "view_mode": "tree,form",
            "res_model": "document.page.link",
            "domain": [("page_id", "=", self.id)],
            "type": "ir.actions.act_window",
            "context": {"default_page_id": self.id},
        }