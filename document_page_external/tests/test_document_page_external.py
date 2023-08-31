# Copyright 2025 Apexive
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from unittest.mock import patch

from odoo.tests import common


class TestDocumentPageExternal(common.TransactionCase):
    """Test the document_page_external functionality."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.page = cls.env.ref("document_page.demo_page1")
        cls.page.external_url = "https://example.com/test"

    @patch("odoo.addons.document_page_external.models.document_page.requests.get")
    def test_retrieve_content(self, mock_get):
        """Test retrieving content from an external URL."""
        # Mock the HTTP response
        mock_response = type(
            "Response",
            (),
            {
                "text": "<p>Test content from external URL</p>",
                "raise_for_status": lambda: None,
            },
        )
        mock_get.return_value = mock_response

        # Directly call the retrieve method
        self.page.action_retrieve_content()

        # Check that a history entry was created
        latest_history = self.env["document.page.history"].search(
            [("page_id", "=", self.page.id)], order="create_date desc, id desc", limit=1
        )
        self.assertEqual(
            latest_history.content, "<p>Test content from external URL</p>"
        )
        self.assertIn("Retrieved from external URL", latest_history.summary)
