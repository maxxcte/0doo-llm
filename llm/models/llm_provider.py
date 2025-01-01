from datetime import datetime

from odoo import _, api, fields, models
from odoo.exceptions import UserError, ValidationError


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

    @api.constrains("name")
    def _check_unique_name(self):
        other_providers = self.search([("id", "not in", self.ids)])
        existing_names_lower = [p.name.lower() for p in other_providers if p.name]
        for record in self:
            if record.name and record.name.lower() in existing_names_lower:
                raise ValidationError(
                    _("The provider name must be unique (case-insensitive).")
                )

        return True

    @property
    def client(self):
        """Get client instance using dispatch pattern"""
        return self._dispatch("get_client")

    def _dispatch(self, method, *args, record=None, **kwargs):
        """Dispatch method call to appropriate service implementation on self or a given record."""
        if not self.service:
            raise UserError(_("Provider service not configured"))

        service_method = f"{self.service}_{method}"
        record = record if record else self
        record_name = record._name

        if not hasattr(record, service_method):
            raise NotImplementedError(
                _("Method '%s' not implemented for service '%s' on target '%s'")
                % (method, self.service, record_name)
            )

        return getattr(record, service_method)(*args, **kwargs)

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

    def chat(self, messages, model=None, stream=False, **kwargs):
        """Send chat messages using this provider"""
        return self._dispatch("chat", messages, model=model, stream=stream, **kwargs)

    def embedding(self, texts, model=None):
        """Generate embeddings using this provider"""
        return self._dispatch("embedding", texts, model=model)

    def list_models(self, model_id=None):
        """List available models from the provider"""
        return self._dispatch("models", model_id=model_id)

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

    @staticmethod
    def serialize_datetime(obj):
        """Helper function to serialize datetime objects to ISO format strings."""
        if isinstance(obj, datetime):
            return obj.isoformat()
        return obj

    @staticmethod
    def serialize_model_data(data: dict) -> dict:
        """
        Recursively process dictionary to serialize datetime objects
        and handle any other non-serializable types.

        Args:
            data (dict): Dictionary potentially containing datetime objects

        Returns:
            dict: Processed dictionary with datetime objects converted to ISO strings
        """
        if not isinstance(data, dict):
            return LLMProvider.serialize_datetime(data)

        return {
            key: LLMProvider.serialize_datetime(value)
            if isinstance(value, datetime)
            else LLMProvider.serialize_model_data(value)
            if isinstance(value, dict)
            else [
                LLMProvider.serialize_model_data(item)
                if isinstance(item, dict)
                else LLMProvider.serialize_datetime(item)
                for item in value
            ]
            if isinstance(value, list)
            else value
            for key, value in data.items()
        }

    def format_tools(self, tools):
        """Format tools for the specific provider"""
        return self._dispatch("format_tools", tools)

    def format_messages(self, messages, system_prompt=None):
        """Format messages for this provider

        Args:
            messages: List of messages to format for specific provider, could be mail.message record set or similar data format
            system_prompt: Optional system prompt to include at the beginning of the messages

        Returns:
            List of formatted messages in provider-specific format
        """
        return self._dispatch("format_messages", messages, system_prompt=system_prompt)
