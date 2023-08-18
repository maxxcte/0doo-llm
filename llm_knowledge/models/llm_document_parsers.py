import base64
import json
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
            ("json", "JSON Parser"),
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
                    # Get the related record
                    record = self.env[document.res_model].browse(document.res_id)
                    if not record.exists():
                        raise UserError(_("Referenced record not found"))

                    # If the record has a specific rag_parse method, call it
                    if hasattr(record, "rag_parse"):
                        success = record.rag_parse(document)
                    else:
                        # Use appropriate parser based on selection
                        if document.parser == "default":
                            success = document._parse_default(record)
                        elif document.parser == "json":
                            success = document._parse_json(record)
                        elif document.parser == "pdf":
                            # Get attachments only if using PDF parser directly
                            attachments = self.env["ir.attachment"].search(
                                [
                                    ("res_model", "=", "llm.document"),
                                    ("res_id", "=", document.id),
                                ],
                                limit=1,
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
                            success = document._parse_default(record)

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

    def _parse_default(self, record):
        """
        Default parser implementation - generates a generic markdown representation
        based on commonly available fields
        """
        self.ensure_one()

        # Start with the record name/display_name if available
        record_name = (
            record.display_name
            if hasattr(record, "display_name")
            else f"{record._name} #{record.id}"
        )
        content = [f"# {record_name}"]

        # Try to include description or common text fields
        common_text_fields = [
            "description",
            "note",
            "comment",
            "message",
            "content",
            "body",
            "text",
        ]
        for field_name in common_text_fields:
            if hasattr(record, field_name) and record[field_name]:
                content.append(f"\n## {field_name.capitalize()}\n")
                content.append(record[field_name])

        # Include a basic info section with simple fields
        info_items = []
        for field_name, field in record._fields.items():
            # Skip binary fields, one2many, many2many, and already included text fields
            if (
                field.type in ["binary", "one2many", "many2many"]
                or field_name in common_text_fields
            ):
                continue

            # Skip technical and internal fields
            if field_name.startswith("_") or field_name in [
                "id",
                "display_name",
                "create_date",
                "create_uid",
                "write_date",
                "write_uid",
            ]:
                continue

            # Get value if it exists and is not empty
            value = record[field_name]
            if value or value == 0:  # Include 0 but not False or None
                if field.type == "many2one" and value:
                    value = value.display_name
                info_items.append(f"- **{field.string}**: {value}")

        if info_items:
            content.append("\n## Information\n")
            content.extend(info_items)

        # Set the content
        self.content = "\n".join(content)

        # Post success message
        self._post_message(
            f"Document parsed using default parser for {record._name}", "success"
        )

        return True

    def _parse_json(self, record):
        """
        JSON parser implementation - converts record data to JSON and then to markdown
        """
        self.ensure_one()

        # Get record name or default to model name and ID
        record_name = (
            record.display_name
            if hasattr(record, "display_name")
            else f"{record._name} #{record.id}"
        )

        # Create a dictionary with record data
        record_data = {}
        for field_name, field in record._fields.items():
            # Skip binary fields and internal fields
            if field.type == "binary" or field_name.startswith("_"):
                continue

            # Handle many2one fields
            if field.type == "many2one" and record[field_name]:
                record_data[field_name] = {
                    "id": record[field_name].id,
                    "name": record[field_name].display_name,
                }
            # Handle many2many and one2many fields
            elif field.type in ["many2many", "one2many"]:
                record_data[field_name] = [
                    {"id": r.id, "name": r.display_name} for r in record[field_name]
                ]
            # Handle other fields
            else:
                record_data[field_name] = record[field_name]

        # Format as markdown
        content = [f"# {record_name}"]
        content.append("\n## JSON Data\n")
        content.append("```json")
        content.append(json.dumps(record_data, indent=2, default=str))
        content.append("```")

        # Update document content
        self.content = "\n".join(content)

        # Post success message
        self._post_message(
            f"Document parsed using JSON parser for {record._name}", "success"
        )

        return True

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
                f"Successfully extracted content from PDF document ({page_count} pages, {image_count} images)",
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
