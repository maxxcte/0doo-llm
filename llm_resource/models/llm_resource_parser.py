import json
import logging

from odoo import _, api, models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMResourceParser(models.Model):
    _inherit = "llm.resource"

    parser = fields.Selection(
        selection="_get_available_parsers",
        string="Parser",
        default="default",
        required=True,
        help="Method used to parse resource content",
        tracking=True,
    )

    @api.model
    def _get_available_parsers(self):
        """Get all available parser methods"""
        return [
            ("default", "Default Parser"),
            ("json", "JSON Parser"),
        ]

    def parse(self):
        """Parse the retrieved content to markdown"""
        # Lock resources and process only the successfully locked ones
        resources = self._lock(state_filter="retrieved")
        if not resources:
            return False

        for resource in resources:
            try:
                # Get the related record
                record = self.env[resource.res_model].browse(resource.res_id)
                if not record.exists():
                    raise UserError(_("Referenced record not found"))

                # If the record has a specific rag_parse method, call it
                if hasattr(record, "llm_parse"):
                    success = record.llm_parse(resource)
                else:
                    if hasattr(record, "llm_get_fields"):
                        for field in record.llm_get_fields():
                            success = resource._parse_field(record, field)
                    else:
                        success = resource._parse_default(record)

                # Only update state if parsing was successful
                if success:
                    resource.write({"state": "parsed"})
                    self.env.cr.commit()  # Force commit the transaction
                    resource._post_message(
                        "Resource successfully parsed", "success"
                    )
                else:
                    resource._post_message(
                        "Parsing completed but did not return success", "warning"
                    )

            except Exception as e:
                _logger.error(
                    "Error parsing resource %s: %s",
                    resource.id,
                    str(e),
                    exc_info=True,
                )
                resource._post_message(f"Error parsing resource: {str(e)}", "error")
            finally:
                resource._unlock()

        # Unlock all successfully processed resources
        resources._unlock()


    def _get_parser(self, record, field_name, mimetype):
        if self.parser != "default":
            return getattr(self, f"parse_{self.parser}")
        if mimetype == "application/pdf":
            return self.parse_pdf
        elif mimetype.startswith("text/"):
                    return self._parse_text
        elif mimetype.startswith("image/"):
                # For images, store a reference in the content
                image_url = f"/web/image/{self.id}"
                llm_resource.content = f"![{self.name}]({image_url})"
                success = True
        elif filename.lower().endswith(".md") or mimetype == "text/markdown":
                success = self._parse_markdown(llm_resource)
                else:
                # Default to a generic description for unsupported types
                llm_resource.content = f"""
                # {self.name}
                
                **File Type**: {mimetype}
                **Description**: This file is of type {mimetype} which cannot be directly parsed into text content.
                **Access**: [Open file](/web/content/{self.id})
                                """
                success = True

                # Post success message if successful
                if success:
                    llm_resource._post_message(
                        f"Successfully parsed attachment: {self.name} ({mimetype})",
                        message_type="success",
                    )

                return success

    def _parse_field(self, record, field):
        self.ensure_one()
        return self._get_parser(record, field_name, mimetype)(record, field)

    def parse_default(self, record, field):
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
            f"Resource parsed using default parser for {record._name}", "success"
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

        # Update resource content
        self.content = "\n".join(content)

        # Post success message
        self._post_message(
            f"Resource parsed using JSON parser for {record._name}", "success"
        )

        return True

    def _parse_pdf(self, record, field):
        """Parse PDF file and extract text and images"""
        # Decode attachment data

        if field[1] != ...... contains "PDF":
            return False


        # Open PDF using PyMuPDF
        text_content = []
        image_count = 0
        page_count = 0

        # Create a BytesIO object from the PDF data
        with pymupdf.open(stream=field[2], filetype="pdf") as doc:
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
                            img_attachment = record.env["ir.attachment"].create(
                                {
                                    "name": image_name,
                                    "datas": base64.b64encode(image_data),
                                    "res_model": "llm.resource",
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

        # Update resource with extracted content
        self.content = final_content

        return True

    def _llm_parse_text(self, record, field_name):
        """Parse plain text file"""
        text_data = base64.b64decode(record.get(field_name,"").decode("utf-8")
        # Format as markdown
        llm_resource.content = text_data


    def _parse_markdown(record, record, field_names):
        """Parse Markdown file"""
        try:
            # Decode binary data as UTF-8 text
            content_bytes = base64.b64decode(record.datas)
            llm_resource.content = content_bytes.decode("utf-8")
            llm_resource._post_message(
                f"Successfully parsed Markdown file: {record.name}",
                message_type="success",
            )
            return True
        except Exception as e:
            raise models.UserError(f"Error parsing Markdown file: {str(e)}") from e