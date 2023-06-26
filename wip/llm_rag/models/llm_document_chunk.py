import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
    embedding_model_id = fields.Many2one(
        related="document_id.embedding_model_id",
        store=True,
        readonly=True,
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

    def vector_search(self, query_vector, limit=10, min_similarity=0.5):
        """
        Search for similar chunks using vector similarity.

        Args:
            query_vector: The query embedding vector
            limit: Maximum number of results to return
            min_similarity: Minimum similarity threshold

        Returns:
            Recordset of matching chunks, ordered by similarity
        """
        chunk_model = self.env["llm.document.chunk"]

        # Prepare domain to search only in the current recordset
        if self:
            domain = [("id", "in", self.ids)]
        else:
            domain = []

        # Use a sample chunk to perform the search
        sample_chunk = chunk_model.search([], limit=1)
        if not sample_chunk:
            return chunk_model

        chunks, _ = sample_chunk.search_similar(
            query_vector=query_vector,
            domain=domain,
            limit=limit,
            min_similarity=min_similarity
        )

        return chunks
