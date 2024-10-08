import logging

from odoo import _, api, models, fields

_logger = logging.getLogger(__name__)


class LLMResourceParser(models.Model):
    _inherit = "llm.resource"

    llm_model_id = fields.Many2one(
        "llm.model",
        string="Model",
        required=False,
        domain="[('model_use', 'in', ['ocr'])]",
        ondelete="restrict",
    )

    llm_provider_id = fields.Many2one(
        "llm.provider",
        string="Provider",
        domain="[('service', '=', 'mistral')]",
        required=False,
        ondelete="restrict",
    )

    @api.model
    def _get_available_parsers(self):
        parsers = super()._get_available_parsers()
        parsers.extend(
            [
                ("mistral_ocr", "Mistral OCR Parser"),
            ]
        )
        return parsers

    def _parse_mistral_ocr(self, file_name, file_path, is_image=False, mime_type=None):
        """
        Parse the resource content using Mistral OCR.
        """
        try:
            if not self.llm_model_id or not self.llm_provider_id:
                raise ValueError("Please select a model and provider.")

            ocr_response = self.llm_provider_id.process_ocr(
                self.llm_model_id.id,
                file_name,
                file_path,
                is_image=is_image,
                mime_type=mime_type
            )
            final_content= self._format_mistral_ocr_text(ocr_response)
            self.content = final_content

            # Post success message - using stored page_count instead of accessing closed doc
            self._post_message(
                f"Successfully extracted content from {file_name} via Mistral OCR",
                "success",
            )

            return True
        except Exception as e:
            self._post_message(
                f"Error parsing resource: {str(e)}",
                "error",
            )
            return False

    
    def _format_mistral_ocr_text(self, ocr_response):
        """Flatten a Mistral OCR response into one big text blob, with page headers."""
        pages = getattr(ocr_response, "pages", [])
        parts = []
        for idx, page in enumerate(pages, start=1):
            parts.append(f"## Page {idx}\n\n{page.markdown.strip()}")
        return "\n\n".join(parts).strip()