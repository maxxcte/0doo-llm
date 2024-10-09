import base64
import logging
import mimetypes
import os
import re
from pathlib import Path

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LLMResourceParser(models.Model):
    _inherit = "llm.resource"

    llm_model_id = fields.Many2one(
        "llm.model",
        string="OCR Model",
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

    def _parse_mistral_ocr(self, file_name, file_path, mimetype):
        """
        Parse the resource content using Mistral OCR.
        """
        try:
            if not self.llm_model_id or not self.llm_provider_id:
                raise ValueError("Please select a model and provider.")

            ocr_response = self.llm_provider_id.process_ocr(
                self.llm_model_id.name, file_name, file_path, mimetype
            )
            final_content = self._format_mistral_ocr_text(ocr_response, file_name)
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

    def _format_mistral_ocr_text(self, ocr_response, file_name):
        """Flatten a Mistral OCR response into one big text blob, with page headers."""
        parts = []
        base_stem = Path(file_name).stem

        for page_idx, page in enumerate(ocr_response.pages, start=1):
            # 1) page header + markdown
            parts.append(f"## Page {page_idx}\n\n{page.markdown.strip()}")

            # 2) each image on that page
            for img in page.images:
                data_uri = img.image_base64 or ""
                if not data_uri:
                    continue

                # split into [ “data:image/jpeg;base64”, “/9j…” ]
                try:
                    header, b64payload = data_uri.split(",", 1)
                except ValueError:
                    _logger.warning("Unexpected image_base64 format: %r", data_uri)
                    continue

                # extract mime type from header: e.g. "data:image/jpeg;base64"
                m = re.match(r"data:([^;]+);base64", header)
                mime = m.group(1) if m else "image/png"

                # guess an extension (".jpeg", ".png", etc.)
                ext = mimetypes.guess_extension(mime) or ".png"

                # decode the payload
                img_bytes = base64.b64decode(b64payload)

                # build a safe filename
                orig_id = img.id  # e.g. "img-0.jpeg"
                stem, _ = os.path.splitext(orig_id)
                image_name = f"{base_stem}_p{page_idx}_{stem}{ext}"

                # create the attachment (Odoo wants its `datas` field as a base64‐string)
                attachment = self.env["ir.attachment"].create(
                    {
                        "name": image_name,
                        "datas": base64.b64encode(img_bytes).decode("ascii"),
                        "res_model": self._name,
                        "res_id": self.id,
                        "mimetype": mime,
                    }
                )

                # inject a Markdown image link
                url = f"/web/image/{attachment.id}/datas"
                parts.append(f"![{image_name}]({url})")

        return "\n\n".join(parts)
