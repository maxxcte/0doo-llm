from odoo import api, fields, models


class CreateResourceWizard(models.TransientModel):
    _name = "llm.create.resource.wizard"
    _description = "Create Resources Wizard"

    record_count = fields.Integer(
        string="Records",
        readonly=True,
        compute="_compute_record_count",
    )
    resource_name_template = fields.Char(
        string="Resource Name Template",
        default="{record_name}",
        help="Template for resource names. Use {record_name}, {model_name}, and {id} as placeholders.",
        required=True,
    )
    process_immediately = fields.Boolean(
        string="Process Immediately",
        default=False,
        help="If checked, resources will be immediately processed through the pipeline",
    )
    state = fields.Selection(
        [
            ("confirm", "Confirm"),
            ("done", "Done"),
        ],
        default="confirm",
    )
    created_resource_ids = fields.Many2many(
        "llm.resource",
        string="Created Resources",
    )
    created_count = fields.Integer(string="Created", compute="_compute_created_count")

    @api.depends("created_resource_ids")
    def _compute_created_count(self):
        for wizard in self:
            wizard.created_count = len(wizard.created_resource_ids)

    @api.depends("record_count")
    def _compute_record_count(self):
        for wizard in self:
            active_ids = self.env.context.get("active_ids", [])
            wizard.record_count = len(active_ids)

    def action_create_resources(self):
        """Create resources for selected records"""
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids", [])

        if not active_model or not active_ids:
            return {"type": "ir.actions.act_window_close"}

        records = self.env[active_model].browse(active_ids)
        model_name = (
            self.env[active_model]._description
            or active_model.replace(".", " ").title()
        )

        # Get the ir.model record for this model
        model_id = (
            self.env["ir.model"].search([("model", "=", active_model)], limit=1).id
        )
        if not model_id:
            return {"type": "ir.actions.act_window_close"}

        created_resources = self.env["llm.resource"]

        for record in records:
            # Get record name - try different common name fields
            record_name = record.display_name
            if not record_name and hasattr(record, "name"):
                record_name = record.name
            if not record_name:
                record_name = f"{model_name} #{record.id}"

            # Format resource name using template
            resource_name = self.resource_name_template.format(
                record_name=record_name,
                model_name=model_name,
                id=record.id,
            )

            # Create resource with model_id instead of res_model
            resource = self.env["llm.resource"].create(
                {
                    "name": resource_name,
                    "model_id": model_id,
                    "res_id": record.id,
                }
            )

            # Process resource if requested
            if self.process_immediately:
                resource.process_resource()

            created_resources |= resource

        self.write(
            {
                "state": "done",
                "created_resource_ids": [(6, 0, created_resources.ids)],
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "llm.create.resource.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def action_view_resources(self):
        """Open the created resources"""
        return {
            "name": "Created Resources",
            "type": "ir.actions.act_window",
            "res_model": "llm.resource",
            "view_mode": "tree,form,kanban",
            "domain": [("id", "in", self.created_resource_ids.ids)],
        }
