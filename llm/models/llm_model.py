from odoo import api, fields, models


class LLMModel(models.Model):
    _name = "llm.model"
    _description = "LLM Model"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True)
    provider_id = fields.Many2one("llm.provider", required=True, ondelete="cascade")
    publisher_id = fields.Many2one(
        "llm.publisher",
        string="Publisher",
        ondelete="restrict",
        tracking=True,
        help="The organization or entity that published this model",
    )

    model_use = fields.Selection(
        selection="_get_available_model_usages",
        required=True,
        default="chat",
    )
    default = fields.Boolean(default=False)
    active = fields.Boolean(default=True)

    # Model details
    details = fields.Json()
    model_info = fields.Json()
    parameters = fields.Text()
    template = fields.Text()

    @api.model
    def _get_available_model_usages(self):
        return [
            ("embedding", "Embedding"),
            ("completion", "Completion"),
            ("chat", "Chat"),
            ("multimodal", "Multimodal"),
        ]

    @api.model_create_multi
    def create(self, vals_list):
        records = super().create(vals_list)
        for record in records:
            if record.default:
                # Ensure only one default per provider/use combo
                self.search(
                    [
                        ("provider_id", "=", record.provider_id.id),
                        ("model_use", "=", record.model_use),
                        ("default", "=", True),
                        ("id", "!=", record.id),
                    ]
                ).write({"default": False})
        return records

    def chat(self, messages, stream=False, **kwargs):
        """Send chat messages using this model"""
        return self.provider_id.chat(messages, model=self, stream=stream, **kwargs)

    def embedding(self, texts):
        """Generate embeddings using this model"""
        return self.provider_id.embedding(texts, model=self)

    def action_open_fetch_this_model_wizard(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": f"Fetch Update for {self.name}",
            "res_model": "llm.fetch.models.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_provider_id": self.provider_id.id,
                "default_model_to_fetch": self.name,
            },
        }
