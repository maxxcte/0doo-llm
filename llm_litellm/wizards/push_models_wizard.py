# wizards/push_models_wizard.py

from odoo import fields, models, api
from odoo.exceptions import UserError


class ModelLine(models.TransientModel):
    _name = "llm.push.models.line"
    _description = "LLM Model Push Line"
    _rec_name = "name"

    wizard_id = fields.Many2one(
        "llm.push.models.wizard",
        required=True,
        ondelete="cascade",
    )
    name = fields.Char(
        string="Model Name",
        required=True,
    )
    provider_id = fields.Many2one(
        "llm.provider",
        string="Provider",
        required=True,
    )
    model_use = fields.Selection(
        [
            ("embedding", "Embedding"),
            ("completion", "Completion"),
            ("chat", "Chat"),
            ("multimodal", "Multimodal"),
        ],
        required=True,
        default="chat",
    )
    status = fields.Selection(
        [
            ("new", "New"),
            ("existing", "Existing"),
            ("modified", "Modified"),
        ],
        required=True,
        default="new",
    )
    selected = fields.Boolean(default=True)
    details = fields.Json()
    existing_model_id = fields.Many2one("llm.model")

    _sql_constraints = [
        (
            "unique_model_per_wizard",
            "UNIQUE(wizard_id, name)",
            "Each model can only be listed once per import.",
        )
    ]


class PushModelsWizard(models.TransientModel):
    _name = "llm.push.models.wizard"
    _description = "Push LLM Models to LiteLLM Proxy"

    provider_id = fields.Many2one(
        "llm.provider",
        required=True,
        readonly=True,
    )
    line_ids = fields.One2many(
        "llm.push.models.line",
        "wizard_id",
        string="Models",
    )
    model_count = fields.Integer(
        compute="_compute_model_count",
        string="Models Found",
    )
    new_count = fields.Integer(
        compute="_compute_model_count",
        string="New Models",
    )
    modified_count = fields.Integer(
        compute="_compute_model_count",
        string="Modified Models",
    )

    @api.depends("line_ids", "line_ids.status")
    def _compute_model_count(self):
        """Compute various model counts for display"""
        for wizard in self:
            wizard.model_count = len(wizard.line_ids)
            wizard.new_count = len(
                wizard.line_ids.filtered(lambda r: r.status == "new")
            )
            wizard.modified_count = len(
                wizard.line_ids.filtered(lambda r: r.status == "modified")
            )

    @api.model
    def default_get(self, fields_list):
        """Load available models from providers"""
        res = super().default_get(fields_list)

        if not self._context.get("active_id"):
            return res

        # Get provider and validate
        provider = self.env["llm.provider"].browse(self._context["active_id"])
        if not provider.exists():
            raise UserError("Provider not found.")

        res["provider_id"] = provider.id

        # Get all models from all providers
        lines = []
        existing_models = {
            model.name: model
            for model in self.env["llm.model"].search([])
        }

        # Map each provider's models to LiteLLM format
        for model in self.env["llm.model"].search([]):
            litellm_name = f"{model.provider_id.service}/{model.name}"

            if not model.provider_id.service:
                continue

            # Check against existing models
            status = "new"
            if litellm_name in existing_models:
                existing = existing_models[litellm_name]
                status = "modified" if existing.details != model.details else "existing"

            lines.append(
                (0, 0, {
                    "name": litellm_name,
                    "provider_id": model.provider_id.id,
                    "model_use": model.model_use,
                    "status": status,
                    "details": model.details,
                    "existing_model_id": existing.id if status != "new" else False,
                })
            )

        if lines:
            res["line_ids"] = lines

        return res

    def action_confirm(self):
        """Create/update selected models in LiteLLM proxy"""
        self.ensure_one()

        selected_lines = self.line_ids.filtered("selected")
        if not selected_lines:
            raise UserError("Please select at least one model to push.")

        # Create/update models via LiteLLM provider
        litellm_provider = self.provider_id
        for line in selected_lines:
            values = {
                "model_name": line.name,
                "litellm_params": {
                    "model": line.name,
                    "custom_llm_provider": line.provider_id.service,
                },
                "model_info": {
                    "id": line.name,
                    "capabilities": [line.model_use],
                    "db_model": False,
                },
            }

            # Update or create model via litellm provider
            litellm_provider.create_model(values)

        # Return success message
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Success",
                "message": f"{len(selected_lines)} models have been pushed to LiteLLM proxy",
                "type": "success",
                "next": {"type": "ir.actions.act_window_close"},
            },
        }