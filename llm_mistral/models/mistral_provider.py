from odoo import api, models


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