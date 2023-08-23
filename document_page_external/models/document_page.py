import logging

import requests

from odoo import _, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class DocumentPage(models.Model):
    """Extend document.page model with external URL functionality."""

    _inherit = "document.page"

    external_url = fields.Char(
        string="External URL",
        help="URL of external content to fetch",
    )

    def action_retrieve_content(self):
        """Directly retrieve content from the external URL."""
        self.ensure_one()
        if not self.external_url:
            raise UserError(_("Please set an external URL first."))

        summary = _("Retrieved from external URL: %s") % self.external_url
        return self.retrieve_from_external_url(summary)

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
                title_match = re.search(r'<title>(.*?)</title>', content, re.IGNORECASE)
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

            return True
        except requests.RequestException as e:
            _logger.error("Error fetching content from %s: %s", self.external_url, e)
            raise UserError(
                _("Failed to retrieve content from URL: %s") % str(e)
            ) from e