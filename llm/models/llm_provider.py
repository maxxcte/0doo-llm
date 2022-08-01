from odoo import _, api, fields, models
from odoo.exceptions import UserError


class LLMProvider(models.Model):
    _name = "llm.provider"
    _inherit = ["mail.thread"]
    _description = "LLM Provider"

    name = fields.Char(required=True)
    service = fields.Selection(
        selection=lambda self: self._selection_service(),
        required=True,
    )
    active = fields.Boolean(default=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        default=lambda self: self.env.company,
    )
    api_key = fields.Char()
    api_base = fields.Char()
    model_ids = fields.One2many("llm.model", "provider_id", string="Models")

    _client = None

    # Service dispatch methods
    def _dispatch(self, method, *args, **kwargs):
        """Dispatch method call to appropriate service implementation"""
        if not self.service:
            raise UserError(_("Provider service not configured"))

        service_method = f"{self.service}_{method}"
        if not hasattr(self, service_method):
            raise NotImplementedError(
                _("Method %s not implemented for service %s") % (method, self.service)
            )

        return getattr(self, service_method)(*args, **kwargs)

    @api.model
    def _selection_service(self):
        """Get all available services from provider implementations"""
        services = []
        for provider in self._get_available_services():
            services.append(provider)
        return services

    @api.model
    def _get_available_services(self):
        """Hook method for registering provider services"""
        return []

    # Common interface methods
    def client(self):
        """Get client instance for the provider"""
        if not self._client:
            self._client = self._dispatch("get_client")
        return self._client

    def chat(self, messages, model=None, stream=False):
        """Send chat messages using this provider"""
        return self._dispatch("chat", messages, model=model, stream=stream)

    def embedding(self, texts, model=None):
        """Generate embeddings using this provider"""
        return self._dispatch("embedding", texts, model=model)

    def list_models(self):
        """List available models from the provider"""
        return self._dispatch("models")

    def get_model(self, model=None, model_use="chat"):
        """Get a model to use for the given purpose

        Args:
            model: Optional specific model to use
            model_use: Type of model to get if no specific model provided

        Returns:
            llm.model record to use
        """
        if model:
            return model

        # Get models from provider
        models = self.model_ids

        # Filter for default model of requested type
        default_models = models.filtered(
            lambda m: m.default and m.model_use == model_use
        )

        if not default_models:
            # Fallback to any model of requested type
            default_models = models.filtered(lambda m: m.model_use == model_use)

        if not default_models:
            raise ValueError(f"No {model_use} model found for provider {self.name}")

        return default_models[0]
