import base64
import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    import pymupdf
except ImportError:
    pymupdf = None

_logger = logging.getLogger(__name__)


class LLMDocumentParser(models.Model):
    _inherit = "llm.document"

    # Selection field for document parser
    parser = fields.Selection(
        selection="_get_available_parsers",
        string="Parser",
        default="default",
        required=True,
        help="Method used to parse document content",
        tracking=True,
    )

    @api.model
    def _get_available_parsers(self):
        """Get all available parser methods"""
        parsers = [
            ("default", "Default Parser"),
        ]
        if pymupdf:  # Only add PDF parser if PyMuPDF is installed
            parsers.append(("pdf", "PDF Parser"))
        return parsers

    def parse(self):
        """Parse the retrieved content to markdown"""
        for document in self:
            if document.state != "retrieved":
                _logger.warning(
                    "Document %s must be in retrieved state to parse content",
                    document.id,
                )
                continue

        # Lock documents and process only the successfully locked ones
        documents = self._lock()
        if not documents:
            return False

        try:
            # Process each document
            for document in documents:
                try:
                    # Use appropriate parser based on selection
                    if document.parser == "default":
                        success = document._parse_default()
                    elif document.parser == "pdf":
                        # Get the related record's attachments
                        attachments = self.env["ir.attachment"].search(
                            [
                                ("res_model", "=", "llm.document"),
                                ("res_id", "=", document.id),
                            ]
                        )
                        if attachments:
                            success = document._parse_pdf(attachments[0])
                        else:
                            raise UserError(_("No PDF attachment found"))
                    else:
                        _logger.warning(
                            "Unknown parser %s, falling back to default",
                            document.parser,
                        )
                        success = document._parse_default()

                    # Only update state if parsing was successful
                    if success:
                        # Debug logging
                        _logger.info(
                            "Parsing successful for document %s, updating state to 'parsed'",
                            document.id,
                        )

                        # Explicitly commit the state change to ensure it's saved
                        document.write({"state": "parsed"})
                        self.env.cr.commit()  # Force commit the transaction

                        document._post_message(
                            "Document successfully parsed", "success"
                        )
                    else:
                        document._post_message(
                            "Parsing completed but did not return success", "warning"
                        )

                except Exception as e:
                    _logger.error(
                        "Error parsing document %s: %s",
                        document.id,
                        str(e),
                        exc_info=True,
                    )
                    document._post_message(f"Error parsing document: {str(e)}", "error")
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
            raise UserError(_("Error in batch parsing: %s") % str(e)) from e

    def _parse_default(self):
        """Default parser implementation - determines file type and calls appropriate parser"""
        self.ensure_one()

        # Get the related record's attachments
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "llm.document"), ("res_id", "=", self.id)]
        )

        if not attachments:
            raise UserError(_("No attachments found for document"))

        # For simplicity, we'll use the first attachment
        attachment = attachments[0]

        # Determine file type based on mimetype
        mimetype = attachment.mimetype or "application/octet-stream"

        if mimetype == "application/pdf":
            return self._parse_pdf(attachment)
        elif mimetype.startswith("text/"):
            return self._parse_text(attachment)
        else:
            raise UserError(_("Unsupported file type: %s") % mimetype)

    def _parse_pdf(self, attachment):
        """Parse PDF file and extract text and images"""
        if not pymupdf:
            raise UserError(
                _(
                    "PyMuPDF library is not installed. Please install it to parse PDF files."
                )
            )

        try:
            # Decode attachment data
            pdf_data = base64.b64decode(attachment.datas)

            # Open PDF using PyMuPDF
            text_content = []
            image_count = 0
            page_count = 0

            # Create a BytesIO object from the PDF data
            with pymupdf.open(stream=pdf_data, filetype="pdf") as doc:
                # Store page count before document is closed
                page_count = doc.page_count

                # Process each page
                for page_num in range(page_count):
                    page = doc[page_num]

                    # Extract text
                    text = page.get_text()
                    text_content.append(f"## Page {page_num + 1}\n\n{text}")

                    # Extract images
                    image_list = page.get_images(full=True)
                    for img_index, img in enumerate(image_list):
                        xref = img[0]
                        try:
                            base_image = doc.extract_image(xref)
                            if base_image:
                                # Store image as attachment
                                image_data = base_image["image"]
                                image_ext = base_image["ext"]
                                image_name = f"image_{page_num}_{img_index}.{image_ext}"

                                # Create attachment for the image
                                img_attachment = self.env["ir.attachment"].create(
                                    {
                                        "name": image_name,
                                        "datas": base64.b64encode(image_data),
                                        "res_model": "llm.document",
                                        "res_id": self.id,
                                        "mimetype": f"image/{image_ext}",
                                    }
                                )

                                # Add image reference to markdown content
                                if img_attachment:
                                    image_url = f"/web/image/{img_attachment.id}"
                                    text_content.append(
                                        f"\n![{image_name}]({image_url})\n"
                                    )
                                    image_count += 1
                        except Exception as e:
                            self._post_message(
                                f"Error extracting image: {str(e)}", "warning"
                            )

            # Join all content
            final_content = "\n\n".join(text_content)

            # Update document with extracted content
            self.content = final_content

            # Post success message - using stored page_count instead of accessing closed doc
            self._post_message(
                f"Successfully extracted content from document ({page_count} pages, {image_count} images)",
                "success",
            )

            return True

        except Exception as e:
            raise UserError(_("Error parsing PDF: %s") % str(e)) from e

    def _parse_text(self, attachment):
        """Parse plain text file"""
        try:
            # Decode attachment data
            text_data = base64.b64decode(attachment.datas).decode("utf-8")

            # Format as markdown
            self.content = text_data

            # Post success message
            self._post_message(
                "Successfully extracted text content from document", "success"
            )
            return True

        except Exception as e:
            raise UserError(_("Error parsing text file: %s") % str(e)) from e