from openai import OpenAI

from odoo import api, models


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    @api.model
    def _get_available_services(self):
        services = super()._get_available_services()
        return services + [("openai", "OpenAI")]

    def openai_get_client(self):
        """Get OpenAI client instance"""
        return OpenAI(api_key=self.api_key, base_url=self.api_base or None)

    def openai_chat(self, messages, model=None, stream=False):
        """Send chat messages using OpenAI"""
        model = self.get_model(model, "chat")

        response = self.client.chat.completions.create(
            model=model.name,
            messages=messages,
            stream=stream,
        )

        if not stream:
            yield {
                "role": response.choices[0].message.role,
                "content": response.choices[0].message.content,
            }
        else:
            for chunk in response:
                if chunk.choices[0].delta.content:
                    yield {
                        "role": "assistant",
                        "content": chunk.choices[0].delta.content,
                    }

    def openai_embedding(self, texts, model=None):
        """Generate embeddings using OpenAI"""
        model = self.get_model(model, "embedding")

        response = self.client.embeddings.create(model=model.name, input=texts)
        return [r.embedding for r in response.data]

    def openai_models(self):
        """List available OpenAI models"""
        models = self.client.models.list()

        for model in models.data:
            # Map model capabilities based on model ID patterns
            capabilities = ["chat"]  # default
            if "text-embedding" in model.id:
                capabilities = ["embedding"]
            elif "gpt-4-vision" in model.id:
                capabilities = ["chat", "multimodal"]

            yield {
                "name": model.id,
                "details": {
                    "id": model.id,
                    "capabilities": capabilities,
                    **model.model_dump(),
                },
            }
