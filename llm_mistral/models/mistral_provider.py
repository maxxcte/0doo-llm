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
