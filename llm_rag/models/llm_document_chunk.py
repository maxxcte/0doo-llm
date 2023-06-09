import json

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
        related="document_id.embedding_model",
        readonly=True,
        store=True,
        help="The model used to create the embedding",
    )
    metadata = fields.Text(
        string="Metadata",
        compute="_compute_metadata",
        store=True,
        help="JSON metadata for this chunk",
    )

    @api.depends("document_id.name", "sequence")
    def _compute_name(self):
        for record in self:
            if record.document_id and record.document_id.name:
                record.name = f"{record.document_id.name} - Chunk {record.sequence}"
            else:
                record.name = f"Chunk {record.sequence}"

    @api.depends(
        "document_id.name",
        "document_id.res_model",
        "document_id.res_id",
        "sequence",
        "document_id.embedding_model",
    )
    def _compute_metadata(self):
        """Compute metadata as a JSON string with information from the document and chunk"""
        for record in self:
            if not record.document_id:
                record.metadata = "{}"
                continue

            # Estimate token count (simplified approach)
            estimated_tokens = len(record.content) // 4 if record.content else 0

            metadata = {
                "document_name": record.document_id.name,
                "res_model": record.document_id.res_model,
                "res_id": record.document_id.res_id,
                "chunk_index": record.sequence,
                "estimated_tokens": estimated_tokens,
                "embedding_model": record.document_id.embedding_model,
            }

            # Add any additional metadata you might need
            record.metadata = json.dumps(metadata)
