from odoo import api, fields, models, _
from odoo.exceptions import UserError
import requests
import logging

_logger = logging.getLogger(__name__)


class DocumentPage(models.Model):
    """Extend document.page model with external URL functionality."""
    _inherit = "document.page"

    external_url = fields.Char(
        string="External URL",
        help="URL of external content to fetch",
    )
    last_external_update = fields.Datetime(
        string="Last External Update",
        readonly=True,
        help="Last time the content was fetched from external URL",
    )

    def action_open_retrieve_wizard(self):
        """Open the retrieve URL wizard."""
        self.ensure_one()
        if not self.external_url:
            raise UserError(_("Please set an external URL first."))

        return {
            'name': _('Retrieve External Content'),
            'type': 'ir.actions.act_window',
            'res_model': 'document.page.retrieve.url',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_page_id': self.id,
                'default_url': self.external_url,
            },
        }

    def retrieve_from_external_url(self, summary=None):
        """Fetch content from external URL and create history entry."""
        self.ensure_one()
        if not self.external_url:
            raise UserError(_("No external URL set for this page."))

        try:
            response = requests.get(self.external_url, timeout=10)
            response.raise_for_status()
            content = response.text

            # Create a history entry with the new content
            history_vals = {
                'page_id': self.id,
                'name': self.draft_name or "1.0",
                'summary': summary or _("Retrieved from external URL: %s") % self.external_url,
                'content': content,
            }
            self._create_history(history_vals)

            # Update last external update timestamp
            self.write({
                'last_external_update': fields.Datetime.now(),
            })

            return True
        except requests.RequestException as e:
            _logger.error("Error fetching content from %s: %s", self.external_url, e)
            raise UserError(_("Failed to retrieve content from URL: %s") % str(e))
