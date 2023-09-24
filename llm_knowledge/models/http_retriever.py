import base64
import logging
import mimetypes
from urllib.parse import urlparse

import requests

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMDocumentRetrieverExtension(models.Model):
    _inherit = "llm.document"

    @api.model
    def _get_available_retrievers(self):
        """Get all available retriever methods"""
        retrievers = super()._get_available_retrievers()
        retrievers.append(("http", "HTTP Retriever"))
        return retrievers

    @api.onchange("res_model", "res_id")
    def _onchange_related_record(self):
        """
        Set HTTP retriever as default when the related record is an attachment with external URL
        """
        if self.res_model == "ir.attachment" and self.res_id:
            attachment = self.env["ir.attachment"].browse(self.res_id)
            if attachment.exists() and attachment.type == "url" and attachment.url:
                self.retriever = "http"


class IrAttachmentExtension(models.Model):
    _inherit = "ir.attachment"

    def rag_retrieve(self, llm_document):
        """
        Override to use HTTP retriever when the attachment has an external URL
        """
        self.ensure_one()

        # If the attachment has a URL and the document uses HTTP retriever, download content
        if self.type == "url" and self.url and llm_document.retriever == "http":
            return self._http_retrieve(llm_document)
        else:
            # Fall back to default behavior
            return (
                super().rag_retrieve(llm_document)
                if hasattr(super(), "rag_retrieve")
                else False
            )

    def _http_retrieve(self, llm_document):
        """
        Retrieves content from an external URL and saves it to the attachment

        :param llm_document: The llm.document record being processed
        :return: Boolean indicating success
        """
        self.ensure_one()
        url = self.url

        if not url:
            llm_document._post_message(
                f"No URL found for attachment {self.name}", "error"
            )
            return False

        try:
            # Log the retrieval attempt
            _logger.info(f"Retrieving content from URL: {url}")

            # Get the content from the URL
            response = requests.get(url, timeout=30)
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

            # Update the attachment with the downloaded content
            filename = self.name or urlparse(url).path.split("/")[-1]
            if not filename:
                filename = "downloaded_file"

            # Prepare extension based on mime type if not in filename
            if "." not in filename:
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    filename += ext

            # Convert the downloaded content to the format required by Odoo (base64)
            content_base64 = base64.b64encode(content)

            # Update the attachment
            self.write(
                {
                    "datas": content_base64,
                    "mimetype": content_type,
                    "name": filename,
                    # Keep the URL but change the type to binary
                    "type": "binary",
                }
            )

            # Update the document
            llm_document._post_message(
                f"Successfully retrieved content from URL: {url} ({len(content)} bytes, {content_type})",
                "success",
            )

            # Mark as retrieved
            llm_document.write({"state": "retrieved"})

            return True

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
