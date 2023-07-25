import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LLMDocumentChunk(models.Model):
    _name = "llm.document.chunk"
    _description = "Document Chunk for RAG"
    _inherit = ["llm.embedding.mixin"]
    _order = "sequence, id"

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
        index=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of the chunk within the document",
    )
    content = fields.Text(
        string="Content",
        required=True,
        help="Chunk text content",
    )
    metadata = fields.Json(
        string="Metadata",
        default={},
        help="Additional metadata for this chunk",
    )

    @api.depends("document_id.name", "sequence")
    def _compute_name(self):
        for chunk in self:
            if chunk.document_id and chunk.document_id.name:
                chunk.name = f"{chunk.document_id.name} - Chunk {chunk.sequence}"
            else:
                chunk.name = f"Chunk {chunk.sequence}"
