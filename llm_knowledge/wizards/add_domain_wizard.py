import json

from odoo import api, fields, models


class AddDomainWizard(models.TransientModel):
    _name = "llm.add.domain.wizard"
    _description = "Add Domain to Collection Wizard"

    collection_id = fields.Many2one(
        "llm.document.collection",
        string="Collection",
        required=True,
        readonly=True,
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Model",
        required=True,
        help="Select the model to which the domain will be applied",
    )
    model_name = fields.Char(
        string="Model Name",
        compute="_compute_model_name",
        store=True,
        help="Technical name of the selected model",
    )
    domain = fields.Char(
        string="Domain",
        default="[]",
        required=True,
        help="Domain filter to select records",
    )

    @api.depends("model_id")
    def _compute_model_name(self):
        """Compute the technical name of the model for the domain widget"""
        for wizard in self:
            wizard.model_name = wizard.model_id.model if wizard.model_id else False

    @api.onchange("model_id")
    def _onchange_model_id(self):
        """Reset domain when model changes"""
        self.domain = "[]"

    def action_add_domain(self):
        """Add the specified domain to the collection's source_domains"""
        self.ensure_one()
        collection = self.collection_id

        # Get the current domains if any
        current_domains = {}
        if collection.source_domains:
            try:
                current_domains = json.loads(collection.source_domains)
            except (json.JSONDecodeError, TypeError):
                current_domains = {}

        # Add the new domain
        model_name = self.model_id.model
        current_domains[model_name] = self.domain

        # Update the collection
        collection.write({"source_domains": json.dumps(current_domains)})

        # Return action to reload the form view
        return {
            "type": "ir.actions.act_window",
            "res_model": "llm.document.collection",
            "res_id": collection.id,
            "view_mode": "form",
            "target": "current",
        }
