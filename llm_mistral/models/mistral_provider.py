from odoo import api, models
from mistralai import Mistral
import logging
import base64

_logger = logging.getLogger(__name__)

class LLMProvider(models.Model):
    _inherit = "llm.provider"

    @api.model
    def _get_available_services(self):
        services = super()._get_available_services()
        return services + [("mistral", "Mistral AI")]

    def _dispatch(self, method, *args, **kwargs):
        return super()._dispatch(method, *args, service_override=("openai" if self.service == "mistral" else None), **kwargs)

    def _dispatch_on_message(self, message_record, method, *args, **kwargs):
        return super()._dispatch_on_message(message_record, method, *args, service_override=("openai" if self.service == "mistral" else None), **kwargs)
        
    def openai_models(self):
        if self.service == "mistral":
            models = self.client.models.list()

            for model in models.data:
                model_json_dump = model.model_dump()
                capabilities = []
                model_caps = model_json_dump["capabilities"]
                if model_caps["vision"]:
                    capabilities.append("multimodal")
                elif model_caps["completion_chat"]:
                    capabilities.append("chat")
                elif "ocr" in model.id:
                    capabilities.append("ocr")
                elif "embed" in model.id:
                    capabilities.append("embedding")
                else:
                    capabilities.append("chat")

                model_json_dump.pop("capabilities", None)
                yield {
                    "name": model.id,
                    "details": {
                        "id": model.id,
                        "capabilities": capabilities,
                        **model_json_dump,
                    },
                }
        else:
            return super().openai_models()
    
    def _get_mistral_client(self):
        self.ensure_one()
        
        return Mistral(
            api_key=self.api_key,
        )
    
    def process_ocr(self, model_id, file_name, file_path, mimetype, **kwargs):
        self.ensure_one()
        model_name = self.model_ids.search([("id", "=", model_id)]).name

        mistral_client = self._get_mistral_client()
        if mimetype.startswith("image/"):
            image_content = self._encode_image(file_path)
            if not image_content:
                raise ValueError("Failed to encode image.")
            return mistral_client.ocr.process(
                model=model_name,
                document={
                    "type": "image_url",
                    "image_url": f"data:{mimetype};base64,{image_content}" 
                },
                include_image_base64=True
            )
        else:
            uploaded_file = mistral_client.files.upload(
                file={
                    "file_name": file_name,
                    "content": open(file_path, "rb"),
                },
                purpose="ocr"
            )
            signed_url = mistral_client.files.get_signed_url(file_id=uploaded_file.id)
            return mistral_client.ocr.process(
                model=model_name,
                document={
                    "type": "document_url",
                    "document_url": signed_url.url,
                },
                include_image_base64=True
            )
    
    def _encode_image(self, image_path):
        """Encode the image to base64."""
        try:
            with open(image_path, "rb") as image_file:
                return base64.b64encode(image_file.read()).decode('utf-8')
        except FileNotFoundError:
            _logger.error(f"The file {image_path} was not found.")
            return None
        except Exception as e:  # Added general exception handling
            _logger.error(f"Error: {e}")
            return None