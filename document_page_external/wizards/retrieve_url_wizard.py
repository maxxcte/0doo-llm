# Copyright 2025 Apexive
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models, _


class DocumentPageRetrieveUrl(models.TransientModel):
    """Wizard to retrieve content from an external URL."""
    _name = "document.page.retrieve.url"
    _description = "Retrieve Content from URL"

    page_id = fields.Many2one(
        'document.page',
        string="Document Page",
        required=True,
        ondelete='cascade',
    )
    url = fields.Char(
        string="URL",
        required=True,
        help="URL to fetch content from",
    )
    summary = fields.Char(
        string="Summary",
        help="Summary of the changes being made",
        default=lambda self: _("Retrieved from external URL"),
    )

    @api.model
    def default_get(self, fields_list):
        """Set default values from the selected page."""
        res = super().default_get(fields_list)
        if self.env.context.get('active_model') == 'document.page':
            page_id = self.env.context.get('active_id')
            if page_id:
                page = self.env['document.page'].browse(page_id)
                res.update({
                    'page_id': page.id,
                    'url': page.external_url,
                })
        return res

    def action_retrieve(self):
        """Execute the retrieval of content from the URL."""
        self.ensure_one()

        # Update the page's external URL if it changed
        if self.url != self.page_id.external_url:
            self.page_id.external_url = self.url

        # Retrieve the content
        self.page_id.retrieve_from_external_url(summary=self.summary)

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Success'),
                'message': _('Content retrieved successfully from external URL.'),
                'sticky': False,
                'type': 'success',
                'next': {
                    'type': 'ir.actions.act_window_close',
                },
            },
        }
