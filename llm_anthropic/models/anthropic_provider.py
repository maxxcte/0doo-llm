from anthropic import Anthropic

from odoo import api, models


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    @api.model
    def _get_available_services(self):
        services = super()._get_available_services()
        return services + [("anthropic", "Anthropic")]

    def anthropic_get_client(self):
        """Get Anthropic client instance"""
        return Anthropic(
            api_key=self.api_key,
        )

    def anthropic_chat(self, messages, model=None, stream=False, **kwargs):
        """Send chat messages using Anthropic"""
        model = self.get_model(model, "chat")

        # Convert messages to Anthropic format
        formatted_messages = []
        system_metadata = None

        for msg in messages:
            if msg["role"] == "system":
                system_metadata = msg["metadata"]
            elif msg["role"] in ["user", "assistant"]:
                formatted_messages.append(
                    {"role": msg["role"], "metadata": msg["metadata"]}
                )

        # Add system message as a parameter if present
        params = {
            "model": model.name,
            "messages": formatted_messages,
            "stream": stream,
            # Defaults to 1024 tokens if not explicitly provided
            "max_tokens": kwargs.get("max_tokens", 1024),
        }
        if system_metadata:
            params["system"] = system_metadata

        # Send chat request
        response = self.client.messages.create(**params)

        if not stream:
            yield {"role": "assistant", "metadata": response.content[0].text}
        else:
            for chunk in response:
                if chunk.type == "content_block_delta":
                    yield {"role": "assistant", "metadata": chunk.delta.text}

    def anthropic_models(self, model_id=None):
        """List available Anthropic models using API endpoint"""
        if model_id:
            model = self.client.models.retrieve(model_id)
            yield self._anthropic_parse_model(model)
        else:
            response = self.client.models.list()

            for model in response.data:
                yield self._anthropic_parse_model(model)

    def _anthropic_parse_model(self, model):
        capabilities = ["chat"]  # All models support chat
        if "multimodal" in model.id.lower() or "claude-3" in model.id.lower():
            capabilities.append("multimodal")

        return {
            "name": model.id,
            "details": {
                "id": model.id,
                "display_name": model.display_name,
                "capabilities": capabilities,
                "created_at": str(model.created_at),
            },
        }
