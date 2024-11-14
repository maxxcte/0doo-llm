import base64
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    import pymupdf
except ImportError:
    pymupdf = None


class IrAttachmentPDFExtension(models.Model):
    _inherit = "ir.attachment"

    def rag_parse(self, llm_resource):
        """
        Override the rag_parse method to handle PDFs if PyMuPDF is available
        """
        self.ensure_one()

        # Determine file type based on mimetype
        mimetype = self.mimetype or "application/octet-stream"

        # If it's a PDF and PyMuPDF is available, use PDF parser
        if mimetype == "application/pdf" and pymupdf:
            return self._parse_pdf(llm_resource)
        else:
            # Otherwise fall back to the base implementation
            return super().rag_parse(llm_resource)

    def _parse_pdf(self, llm_resource):
        """Parse PDF file and extract text and images"""
        if not pymupdf:
            raise UserError(
                _(
                    "PyMuPDF library is not installed. Please install it to parse PDF files."
                )
            )

        try:
            # Decode attachment data
            pdf_data = base64.b64decode(self.datas)

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
                                        "res_model": "llm.resource",
                                        "res_id": llm_resource.id,
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
                            llm_resource._post_message(
                                f"Error extracting image: {str(e)}", "warning"
                            )

            # Join all content
            final_content = "\n\n".join(text_content)

            # Update resource with extracted content
            llm_resource.content = final_content

            # Post success message - using stored page_count instead of accessing closed doc
            llm_resource._post_message(
                f"Successfully extracted content from PDF document ({page_count} pages, {image_count} images)",
                "success",
            )

            return True

        except Exception as e:
            raise UserError(_("Error parsing PDF: %s") % str(e)) from e
