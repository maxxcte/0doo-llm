import base64
import logging
import mimetypes
import re
from urllib.parse import urljoin, urlparse

import requests
from markdownify import markdownify as md

from odoo import api, models

_logger = logging.getLogger(__name__)

# Regex to find meta refresh tags
# Handles single or double quotes around url and content values
META_REFRESH_RE = re.compile(
    r"""<meta[^>]*http-equiv\s*=\s*["']?refresh["']?[^>]*content\s*=\s*["']?\d+\s*;\s*url=([^"'>]+)["']?""",
    re.IGNORECASE | re.DOTALL,
)


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
        # Check if HTTP retriever should be used
        if llm_resource.retriever == "http" and self.url:
            _logger.info(
                "Using HTTP retriever for attachment %s (url: %s)", self.name, self.url
            )
            return self._http_retrieve(llm_resource)
        else:
            # Fall back to default behavior if not HTTP or no URL
            _logger.info(
                "Falling back to default retriever for attachment %s (type: %s, url: %s, resource retriever: %s)",
                self.name,
                self.type,
                self.url,
                llm_resource.retriever,
            )
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
        # Regex to find markdown links: [text](url)
        link_pattern = r"\[([^\]]+)\]\(([^)]+)\)"

        def replace_link(match):
            text = match.group(1)
            url = match.group(2)

            # Join if URL is relative (doesn't start with known schemes)
            if not url.startswith(("http://", "https://", "mailto:", "tel:")):
                try:
                    full_url = urljoin(base_url, url)
                    return f"[{text}]({full_url})"
                except ValueError:
                    # Handle potential errors in urljoin, e.g., bad base URL
                    _logger.warning(
                        f"Could not join base URL '{base_url}' with relative URL '{url}'. Keeping relative link."
                    )
                    return match.group(0)  # Keep original link
            return match.group(0)  # Keep absolute link as is

        # Replace all markdown links with full URLs
        return re.sub(link_pattern, replace_link, markdown_content)

    def _is_text_content_type(self, content_type):
        """
        Check if the content type is a text type that can be processed directly.

        :param content_type: MIME type to check (e.g., 'text/html')
        :return: Boolean indicating if it's a text content type
        """
        text_types = [
            "text/html",
            "text/plain",
            "text/markdown",
            "application/xhtml+xml",
            "application/xml",
            "application/json", # Added JSON as text
            "application/javascript", # Added JS as text
        ]
        # Check if the main type (before any ';') starts with a known text type
        main_type = content_type.split(";")[0].strip()
        return any(main_type.startswith(t) for t in text_types)

    def _http_retrieve(self, llm_resource):
        """
        Retrieves content from an external URL, handling redirects and meta refreshes.
        For HTML, text, or markdown content, directly updates the llm.resource content.
        For binary content, downloads and saves it to the attachment.

        :param llm_resource: The llm.resource record being processed
        :return: Dictionary with state or Boolean indicating success
        """
        self.ensure_one()
        initial_url = self.url
        max_refreshes = 1  # Limit meta refreshes to prevent loops

        if not initial_url:
            llm_resource._post_styled_message(
                f"No URL found for attachment {self.name}", "error"
            )
            return False

        _logger.info(f"Retrieving content from initial URL: {initial_url}")
        headers = {"User-Agent": "Mozilla/5.0 (compatible; Odoo LLM Resource/1.0)"}

        try:
            # Initial request, allow standard HTTP redirects
            response = requests.get(
                initial_url, timeout=30, headers=headers, allow_redirects=True
            )
            response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)

            current_url = response.url  # URL after standard redirects
            if current_url != initial_url:
                _logger.info(f"Initial URL '{initial_url}' redirected to '{current_url}'.")

            content = response.content
            content_type_header = response.headers.get("Content-Type", "")
            content_type = content_type_header.split(";")[0].strip()

            # --- Meta Refresh Handling ---
            refreshes_followed = 0
            while refreshes_followed < max_refreshes:
                if self._is_text_content_type(content_type):
                    try:
                        # Decode temporarily to check for meta refresh tag
                        temp_text_content = content.decode(
                            response.encoding or "utf-8", errors="ignore"
                        )
                        meta_match = META_REFRESH_RE.search(temp_text_content)

                        if meta_match:
                            refresh_target_relative = meta_match.group(1).strip()
                            # Resolve relative URL against the URL that provided the meta tag
                            refresh_target_absolute = urljoin(
                                current_url, refresh_target_relative
                            )
                            _logger.info(
                                f"Detected meta refresh. Following from '{current_url}' to '{refresh_target_absolute}'"
                            )

                            # Make the new request for the refreshed URL
                            response = requests.get(
                                refresh_target_absolute,
                                timeout=30,
                                headers=headers,
                                allow_redirects=True,
                            )
                            response.raise_for_status()

                            # Update state with the new response
                            new_current_url = response.url
                            if new_current_url != refresh_target_absolute:
                                _logger.info(
                                    f"Meta refresh target '{refresh_target_absolute}' redirected to '{new_current_url}'."
                                )
                            current_url = new_current_url # Update current_url after potential redirect on refresh target
                            content = response.content
                            content_type_header = response.headers.get("Content-Type", "")
                            content_type = content_type_header.split(";")[0].strip()

                            refreshes_followed += 1
                            continue  # Re-check the new content for another refresh (up to limit)
                        else:
                            break  # No meta refresh found in this content
                    except Exception as e:
                        # Log potential decoding or regex errors during check
                        _logger.warning(
                            f"Error during meta refresh check for {current_url}: {e}"
                        )
                        break  # Stop checking if error occurs
                else:
                    break  # Not text content, cannot contain meta refresh
            # --- End Meta Refresh Handling ---

            final_url = current_url  # The URL after all redirects/refreshes

            # Update the attachment URL if it changed from the initial one
            if final_url != initial_url:
                _logger.info(f"Updating attachment URL from '{initial_url}' to final URL '{final_url}'.")
                self.write({'url': final_url})

            # Determine the final mime type if not provided or unclear
            if not content_type:
                content_type, _ = mimetypes.guess_type(final_url)
            if not content_type:
                _logger.warning(f"Could not determine mime type for {final_url}. Defaulting to octet-stream.")
                content_type = "application/octet-stream"

            # Generate filename
            parsed_url = urlparse(final_url)
            filename = self.name or parsed_url.path.split("/")[-1] or "downloaded_file"
            if "." not in filename:
                ext = mimetypes.guess_extension(content_type)
                if ext:
                    filename += ext

            # --- Process Final Content ---
            if self._is_text_content_type(content_type):
                _logger.info(f"Processing final text content ({len(content)} bytes) from {final_url}")
                try:
                    # Decode final content using detected or fallback encodings
                    text_content = content.decode(response.encoding or "utf-8")
                except UnicodeDecodeError:
                    _logger.warning(f"UTF-8 decoding failed for {final_url}. Trying fallbacks.")
                    # Try common fallbacks
                    for encoding in ["latin-1", "windows-1252", "iso-8859-1"]:
                        try:
                            text_content = content.decode(encoding)
                            _logger.info(f"Successfully decoded using {encoding}.")
                            break
                        except UnicodeDecodeError:
                            continue
                    else:
                        _logger.error(f"Failed to decode content from {final_url} with any supported encoding.")
                        # Store raw binary data if decoding fails completely
                        text_content = None

                if text_content is not None:
                    # Convert HTML/XHTML to Markdown
                    if content_type.startswith(("text/html", "application/xhtml+xml")):
                        _logger.info("Converting HTML/XHTML content to Markdown.")
                        try:
                            markdown_content = md(text_content)
                        except Exception as e:
                            _logger.error(f"Markdownify conversion failed for {final_url}: {e}")
                            markdown_content = text_content # Fallback to original text
                    else:
                        # Keep plain text, markdown, json, etc. as is
                        markdown_content = text_content

                    # Ensure links are absolute
                    markdown_content = self._ensure_full_urls(markdown_content, final_url)
                    _logger.info(f"Final processed text length: {len(markdown_content)} characters.")

                    # Update the llm.resource with the processed text
                    llm_resource.write({"content": markdown_content})
                else:
                    # Handle case where decoding failed
                    llm_resource._post_styled_message(
                        f"Failed to decode text content from URL: {final_url}. Storing raw data.",
                        "warning",
                    )
                    llm_resource.write({"content": ""}) # Clear content if unreadable

                # Store final (potentially raw if decode failed) content in attachment
                content_base64 = base64.b64encode(content)
                self.write(
                    {
                        "datas": content_base64,
                        "mimetype": content_type,
                        "name": filename,
                        "type": "binary",  # Keep as binary after download
                    }
                )

                llm_resource._post_styled_message(
                    f"Successfully retrieved and processed text content from URL: {final_url} (original: {initial_url})",
                    "success",
                )
                return {"state": "parsed"}
            else:
                # Handle binary content
                _logger.info(f"Saving final binary content ({len(content)} bytes, type: {content_type}) from {final_url}")
                content_base64 = base64.b64encode(content)
                self.write(
                    {
                        "datas": content_base64,
                        "mimetype": content_type,
                        "name": filename,
                        "type": "binary",  # Keep as binary
                    }
                )
                llm_resource._post_styled_message(
                    f"Successfully retrieved binary content from URL: {final_url} (original: {initial_url})",
                    "success",
                )
                # Binary content needs further specific parsing
                return {"state": "retrieved"}

        except requests.exceptions.RequestException as e:
            llm_resource._post_styled_message(
                f"HTTP request failed for URL {initial_url}: {e}", "error"
            )
            _logger.error(f"HTTP request failed for URL {initial_url}: {e}")
            return False
        except Exception as e:
            # Catch any other unexpected errors during processing
            llm_resource._post_styled_message(
                f"An unexpected error occurred during HTTP retrieval from {initial_url}: {e}",
                "error",
            )
            _logger.exception(
                f"Unexpected error during HTTP retrieval from {initial_url}"
            )
            return False
