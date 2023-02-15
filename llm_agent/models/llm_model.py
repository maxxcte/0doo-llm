from odoo import models


class LLMModel(models.Model):
    _inherit = "llm.model"

    def chat(self, messages, stream=False, tools=None, tool_choice="auto"):
        """Send chat messages using this model"""
        return self.provider_id.chat(
            messages, model=self, stream=stream, tools=tools, tool_choice=tool_choice
        )

    def embedding(self, texts):
        """Generate embeddings using this model"""
        return self.provider_id.embedding(texts, model=self)
