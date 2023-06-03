from odoo import api, fields, models


class CreateRAGDocumentWizard(models.TransientModel):
    _name = "llm.create.rag.document.wizard"
    _description = "Create RAG Documents Wizard"

    record_count = fields.Integer(
        string="Records",
        readonly=True,
        compute="_compute_record_count",
    )
    document_name_template = fields.Char(
        string="Document Name Template",
        default="{record_name}",
        help="Template for document names. Use {record_name}, {model_name}, and {id} as placeholders.",
        required=True,
    )
    process_immediately = fields.Boolean(
        string="Process Immediately",
        default=False,
        help="If checked, documents will be immediately processed through the RAG pipeline",
    )
    state = fields.Selection(
        [
            ("confirm", "Confirm"),
            ("done", "Done"),
        ],
        default="confirm",
    )
    created_document_ids = fields.Many2many(
        "llm.document",
        string="Created Documents",
    )
    created_count = fields.Integer(string="Created", compute="_compute_created_count")

    @api.depends("created_document_ids")
    def _compute_created_count(self):
        for wizard in self:
            wizard.created_count = len(wizard.created_document_ids)

    @api.depends("record_count")
    def _compute_record_count(self):
        for wizard in self:
            active_ids = self.env.context.get("active_ids", [])
            wizard.record_count = len(active_ids)

    def action_create_documents(self):
        """Create RAG documents for selected records"""
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids", [])

        if not active_model or not active_ids:
            return {"type": "ir.actions.act_window_close"}

        records = self.env[active_model].browse(active_ids)
        model_name = (
            self.env[active_model]._description
            or active_model.replace(".", " ").title()
        )

        created_documents = self.env["llm.document"]

        for record in records:
            # Get record name - try different common name fields
            record_name = record.display_name
            if not record_name and hasattr(record, "name"):
                record_name = record.name
            if not record_name:
                record_name = f"{model_name} #{record.id}"

            # Format document name using template
            document_name = self.document_name_template.format(
                record_name=record_name,
                model_name=model_name,
                id=record.id,
            )

            # Create RAG document
            document = self.env["llm.document"].create(
                {
                    "name": document_name,
                    "res_model": active_model,
                    "res_id": record.id,
                }
            )

            # Process document if requested
            if self.process_immediately:
                document.process_document()

            created_documents |= document

        self.write(
            {
                "state": "done",
                "created_document_ids": [(6, 0, created_documents.ids)],
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "llm.create.rag.document.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def action_view_documents(self):
        """Open the created documents"""
        return {
            "name": "Created RAG Documents",
            "type": "ir.actions.act_window",
            "res_model": "llm.document",
            "view_mode": "tree,form,kanban",
            "domain": [("id", "in", self.created_document_ids.ids)],
        }
