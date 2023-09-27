import logging
import re
from urllib.parse import urljoin

import markdown
import requests
from markdownify import markdownify as md

from odoo import _, fields, models

_logger = logging.getLogger(__name__)


class DocumentPage(models.Model):
    _inherit = "document.page"

    external_url = fields.Char(
        string="External URL",
        help="External URL to fetch content from",
        tracking=True,
    )

    def action_retrieve_external_content(self):
        """
        Action method to retrieve content from external URL.
        This method will check if an LLM document exists for the page,
        create one if it doesn't, and then call rag_retrieve.

        :return: Dictionary with action result or notification
        """
        self.ensure_one()

        if not self.external_url:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Warning"),
                    "message": _("No external URL defined for document page"),
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Check if llm.document exists for this record
        LlmDocument = self.env["llm.document"]
        doc = LlmDocument.search(
            [("res_model", "=", "document.page"), ("res_id", "=", self.id)], limit=1
        )

        # Create llm.document if it doesn't exist
        if not doc:
            doc = LlmDocument.create(
                {
                    "name": self.name,
                    "res_model": "document.page",
                    "res_id": self.id,
                }
            )
        doc.write({"state": "draft"})
        doc.retrieve()

    def rag_retrieve(self, llm_document):
        """
        Implementation of rag_retrieve for document.page model.
        This method retrieves the content from external URL if present,
        otherwise uses the existing content.

        :param llm_document: The llm.document record being processed
        :return: Boolean indicating success
        """
        self.ensure_one()

        if self.external_url:
            # Use HTTP retriever for external URL
            return self._http_retrieve(llm_document)

    def _ensure_full_urls(self, markdown_content, base_url):
        """
        Ensure all links in markdown content have full URLs.

        :param markdown_content: Markdown content to process
        :param base_url: Base URL to prepend to relative URLs
        :return: Markdown content with full URLs
        """
        # Regex to find markdown links
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"

        def replace_link(match):
            text = match.group(1)
            url = match.group(2)

            # If URL doesn't start with http:// or https://, it's relative
            if not url.startswith(("http://", "https://", "mailto:", "tel:")):
                full_url = urljoin(base_url, url)
                return f"[{text}]({full_url})"
            return match.group(0)

        # Replace all markdown links with full URLs
        return re.sub(link_pattern, replace_link, markdown_content)

    def _http_retrieve(self, llm_document):
        """
        Retrieves content from an external URL, converts it to markdown,
        and updates both the LLM document and the page content.
        Ensures all markdown links have full URLs.

        :param llm_document: The llm.document record being processed
        :return: Boolean indicating success
        """
        self.ensure_one()
        url = self.external_url

        if not url:
            llm_document._post_message(
                f"No external URL defined for document page {self.name}", "error"
            )
            return False

        try:
            # Log the retrieval attempt
            _logger.info(f"Retrieving content from URL: {url}")

            # Get the content from the URL
            response = requests.get(url, timeout=30)
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Get content type and text content
            content_type = response.headers.get("Content-Type", "")
            html_content = response.text

            # Convert HTML to markdown for the LLM document
            markdown_content = md(html_content)

            # Ensure all links have full URLs
            markdown_content = self._ensure_full_urls(markdown_content, url)

            # Update the LLM document with markdown content
            llm_document.write({"content": markdown_content})

            # Update the document page with HTML content
            # Note: We're storing the HTML in the document page for better display
            self.write(
                {
                    "content": markdown.markdown(markdown_content),
                }
            )

            # Post success message
            llm_document._post_message(
                f"Successfully retrieved and parsed content from URL: {url} ({len(html_content)} bytes)",
                "success",
            )

            return {"state": "parsed"}

        except requests.RequestException as e:
            error_msg = f"Error retrieving content from URL {url}: {str(e)}"
            _logger.error(error_msg)
            llm_document._post_message(error_msg, "error")
            return False
        except Exception as e:
            error_msg = f"Unexpected error processing URL {url}: {str(e)}"
            _logger.error(error_msg, exc_info=True)
            llm_document._post_message(error_msg, "error")
            return False
