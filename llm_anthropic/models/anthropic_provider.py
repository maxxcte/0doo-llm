from anthropic import Anthropic

from odoo import models, api


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

    def anthropic_chat(self, messages, model=None, stream=False):
        """Send chat messages using Anthropic"""
        model = self.get_model(model, "chat")

        # Convert messages to Anthropic format
        formatted_messages = []
        system_content = None

        for msg in messages:
            if msg["role"] == "system":
                system_content = msg["content"]
            elif msg["role"] in ["user", "assistant"]:
                formatted_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        # Add system message as a parameter if present
        params = {
            "model": model.name,
            "messages": formatted_messages,
            "stream": stream,
        }
        if system_content:
            params["system"] = system_content

        # Send chat request
        response = self.client.messages.create(**params)

        if not stream:
            yield {
                "role": "assistant",
                "content": response.content[0].text
            }
        else:
            for chunk in response:
                if chunk.type == "content_block_delta":
                    yield {
                        "role": "assistant",
                        "content": chunk.delta.text
                    }

    def anthropic_models(self):
        """List available Anthropic models using API endpoint"""
        response = self.client.models.list()

        for model in response.data:
            # Determine capabilities based on model properties
            capabilities = ["chat"]  # All models support chat
            if "multimodal" in model.id.lower() or "claude-3" in model.id.lower():
                capabilities.append("multimodal")


            yield {
                "name": model.id,
                "details": {
                    "id": model.id,
                    "display_name": model.display_name,
                    "capabilities": capabilities,
                    "created_at": str(model.created_at),
                }
            }
