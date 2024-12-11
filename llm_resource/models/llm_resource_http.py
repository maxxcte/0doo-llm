import base64
import logging
import mimetypes
import re
from urllib.parse import urljoin, urlparse

import requests
from markdownify import markdownify as md

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMResourceHTTPRetriever(models.Model):
    _inherit = "llm.resource"

    @api.model
    def _get_available_retrievers(self):
        """Get all available retriever methods"""
        retrievers = super()._get_available_retrievers()
        retrievers.append(("http", "HTTP Retriever"))
        return retrievers


class IrAttachmentExtension(models.Model):
    _inherit = "ir.attachment"

    def rag_retrieve(self, llm_resource):
        """
        Implementation for HTTP retrieval when the attachment has an external URL
        """
        self.ensure_one()

        # If the attachment has a URL and the resource uses HTTP retriever, download content
        if self.type == "url" and self.url:
            return self._http_retrieve(llm_resource)
        else:
            # Fall back to default behavior
            return (
                super().rag_retrieve(llm_resource)
                if hasattr(super(), "rag_retrieve")
                else False
            )

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

    def _is_text_content_type(self, content_type):
        """
        Check if the content type is a text type that can be processed directly.

        :param content_type: MIME type to check
        :return: Boolean indicating if it's a text content type
        """
        text_types = [
            "text/html",
            "text/plain",
            "text/markdown",
            "application/xhtml+xml",
            "application/xml",
        ]
        return any(content_type.startswith(t) for t in text_types)

    def _http_retrieve(self, llm_resource):
        """
        Retrieves content from an external URL.
        For HTML, text, or markdown content, directly updates the llm.resource content.
        For binary content, downloads and saves it to the attachment.

        :param llm_resource: The llm.resource record being processed
        :return: Dictionary with state or Boolean indicating success
        """
        self.ensure_one()
        url = self.url

        if not url:
            llm_resource._post_styled_message(
                f"No URL found for attachment {self.name}", "error"
            )
            return False

        # Log the retrieval attempt
        _logger.info(f"Retrieving content from URL: {url}")

        # Get the content from the URL
        headers = {"User-Agent": "Mozilla/5.0 (compatible; Odoo LLM Resource/1.0)"}
        response = requests.get(url, timeout=30, headers=headers)
        response.raise_for_status()  # Raise an exception for HTTP errors

        # Get the content
        content = response.content

        # Determine the mime type
        content_type = response.headers.get("Content-Type", "")
        # Extract the main mime type without parameters
        if ";" in content_type:
            content_type = content_type.split(";")[0].strip()

        if not content_type:
            # Try to guess from URL if Content-Type header is missing
            content_type, _ = mimetypes.guess_type(url)

        if not content_type:
            # Default to octet-stream if we still can't determine
            content_type = "application/octet-stream"

        # Get filename from the URL or attachment name
        filename = self.name or urlparse(url).path.split("/")[-1]
        if not filename:
            filename = "downloaded_file"

        # Prepare extension based on mime type if not in filename
        if "." not in filename:
            ext = mimetypes.guess_extension(content_type)
            if ext:
                filename += ext

        # Handle based on content type
        if self._is_text_content_type(content_type):
            # For text content types, extract the text and update the llm.resource
            try:
                text_content = content.decode("utf-8")
            except UnicodeDecodeError:
                # Try other common encodings
                for encoding in ["latin-1", "windows-1252", "iso-8859-1"]:
                    try:
                        text_content = content.decode(encoding)
                        break
                    except UnicodeDecodeError:
                        continue
                else:
                    raise UnicodeDecodeError(
                        "Failed to decode content with any supported encoding"
                    )

            # Convert HTML to markdown if it's HTML content
            if content_type.startswith(("text/html", "application/xhtml+xml")):
                markdown_content = md(text_content)
            else:
                # For plain text or already markdown, keep as is
                markdown_content = text_content

            # Ensure all links have full URLs
            markdown_content = self._ensure_full_urls(markdown_content, url)

            # Update the llm.resource with markdown content
            llm_resource.write({"content": markdown_content})

            # Store as attachment anyway for reference
            content_base64 = base64.b64encode(content)
            self.write(
                {
                    "datas": content_base64,
                    "mimetype": content_type,
                    "name": filename,
                    "type": "binary",
                }
            )

            # Post success message
            llm_resource._post_styled_message(
                f"Successfully retrieved and parsed content from URL: {url} ({len(text_content)} characters)",
                "success",
            )

            # Since we've already parsed the content, return parsed state
            return {"state": "parsed"}
        else:
            # For binary content, save to attachment
            content_base64 = base64.b64encode(content)
            self.write(
                {
                    "datas": content_base64,
                    "mimetype": content_type,
                    "name": filename,
                    "type": "binary",
                }
            )

            # Post success message
            llm_resource._post_styled_message(
                f"Successfully retrieved content from URL: {url} ({len(content)} bytes, {content_type})",
                "success",
            )

            # Binary content still needs parsing
            return {"state": "retrieved"}
