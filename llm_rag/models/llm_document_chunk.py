from odoo import api, fields, models


class LLMDocumentChunk(models.Model):
    _name = "llm.document.chunk"
    _description = "LLM Document Chunk"
    _order = "sequence"

    name = fields.Char(
        string="Name",
        compute="_compute_name",
        store=True,
    )
    document_id = fields.Many2one(
        "llm.document",
        string="Document",
        required=True,
        ondelete="cascade",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
    )
    content = fields.Text(
        string="Content",
        required=True,
        help="The content of this document chunk",
    )
    embedding = fields.Binary(
        string="Embedding",
        attachment=True,
        help="Vector embedding for this chunk",
    )
    embedding_model = fields.Char(
        string="Embedding Model",
        help="The model used to create the embedding",
    )

    @api.depends("document_id.name", "sequence")
    def _compute_name(self):
        for record in self:
            if record.document_id and record.document_id.name:
                record.name = f"{record.document_id.name} - Chunk {record.sequence}"
            else:
                record.name = f"Chunk {record.sequence}"
