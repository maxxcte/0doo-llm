from odoo import models, _


class IrAttachment(models.Model):
    _inherit = "ir.attachment"

    def rag_parse(self, llm_document):
        """
        Implementation of rag_parse for ir.attachment model.
        This method determines the attachment type and uses the appropriate parser.

        :param llm_document: The llm.document record being processed
        :return: Boolean indicating success
        """
        self.ensure_one()

        # Determine file type based on mimetype
        mimetype = self.mimetype or "application/octet-stream"

        try:
            # Handle different file types
            if mimetype == "application/pdf":
                success = llm_document._parse_pdf(self)
            elif mimetype.startswith("text/"):
                success = llm_document._parse_text(self)
            elif mimetype.startswith("image/"):
                # For images, store a reference in the content
                image_url = f"/web/image/{self.id}"
                llm_document.content = f"![{self.name}]({image_url})"
                success = True
            else:
                # Default to a generic description for unsupported types
                llm_document.content = f"""
# {self.name}

**File Type**: {mimetype}
**Description**: This file is of type {mimetype} which cannot be directly parsed into text content.
**Access**: [Open file](/web/content/{self.id})
                """
                success = True

            # Post success message if successful
            if success:
                llm_document.message_post(
                    body=f"Successfully parsed attachment: {self.name} ({mimetype})",
                    message_type="success",
                )

            return success

        except Exception as e:
            llm_document.message_post(
                body=f"Error parsing attachment: {str(e)}",
                message_type="error",
            )
            return False
