import base64
from odoo import models


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def rag_parse(self, llm_resource):
        """
        Implementation of rag_parse for ir.attachment model.
        This method determines the attachment type and uses the appropriate parser.

        :param llm_resource: The llm.resource record being processed
        :return: Boolean indicating success
        """
        self.ensure_one()

        # Determine file type based on mimetype
        mimetype = self.mimetype or "application/octet-stream"
        filename = self.name or ""

        try:
            # Handle different file types
            if mimetype == "application/pdf":
                # PDF handling will be provided by llm_knowledge
                llm_resource.content = f"""
# {self.name}

**File Type**: {mimetype}
**Description**: This is a PDF file that requires the llm_knowledge module for full text extraction.
**Access**: [Open file](/web/content/{self.id})
                """
                success = True
            elif mimetype.startswith("text/"):
                success = self._parse_text(llm_resource)
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

        except Exception as e:
            llm_resource._post_message(
                f"Error parsing attachment: {str(e)}",
                message_type="error",
            )
            return False

    def _parse_text(self, llm_resource):
        """Parse plain text file"""
        try:
            # Decode attachment data
            text_data = base64.b64decode(self.datas).decode("utf-8")

            # Format as markdown
            llm_resource.content = text_data

            # Post success message
            llm_resource._post_message(
                "Successfully extracted text content from document", "success"
            )
            return True

        except Exception as e:
            raise models.UserError(f"Error parsing text file: {str(e)}") from e

    def _parse_markdown(self, llm_resource):
        """Parse Markdown file"""
        try:
            # Decode binary data as UTF-8 text
            content_bytes = base64.b64decode(self.datas)
            llm_resource.content = content_bytes.decode("utf-8")
            llm_resource._post_message(
                f"Successfully parsed Markdown file: {self.name}",
                message_type="success",
            )
            return True
        except Exception as e:
            raise models.UserError(f"Error parsing Markdown file: {str(e)}") from e