# Copyright 2025 Apexive
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo.tests import common
from unittest.mock import patch


class TestDocumentPageExternal(common.TransactionCase):
    """Test the document_page_external functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.page = cls.env.ref('document_page.demo_page1')
        cls.page.external_url = "https://example.com/test"

    def test_wizard_default_get(self):
        """Test the wizard's default_get method."""
        wizard = self.env['document.page.retrieve.url'].with_context(
            active_model='document.page',
            active_id=self.page.id
        ).create({})

        self.assertEqual(wizard.page_id, self.page)
        self.assertEqual(wizard.url, self.page.external_url)

    @patch('odoo.addons.document_page_external.models.document_page.requests.get')
    def test_retrieve_content(self, mock_get):
        """Test retrieving content from an external URL."""
        # Mock the HTTP response
        mock_response = type('Response', (), {
            'text': '<p>Test content from external URL</p>',
            'raise_for_status': lambda: None,
        })
        mock_get.return_value = mock_response

        # Create and process the wizard
        wizard = self.env['document.page.retrieve.url'].create({
            'page_id': self.page.id,
            'url': self.page.external_url,
            'summary': 'Test retrieving content',
        })
        wizard.action_retrieve()

        # Check that a history entry was created
        latest_history = self.env['document.page.history'].search(
            [('page_id', '=', self.page.id)],
            order='create_date desc, id desc',
            limit=1
        )
        self.assertEqual(latest_history.content, '<p>Test content from external URL</p>')
        self.assertEqual(latest_history.summary, 'Test retrieving content')

        # Check that last_external_update was updated
        self.assertTrue(self.page.last_external_update)
