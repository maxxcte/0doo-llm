import logging
from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LLMKnowledgeChunkEmbedding(models.Model):
    _name = "llm.knowledge.chunk.embedding"
    _description = "Vector Embedding for Knowledge Chunks"

    chunk_id = fields.Many2one(
        "llm.knowledge.chunk",
        string="Chunk",
        required=True,
        ondelete="cascade",
        index=True,
    )
    collection_id = fields.Many2one(
        "llm.knowledge.collection",
        string="Collection",
        required=True,
        ondelete="cascade",
        index=True,
    )
    embedding_model_id = fields.Many2one(
        "llm.model",
        string="Embedding Model",
        domain="[('model_use', '=', 'embedding')]",
        required=True,
        ondelete="restrict",
        index=True,
    )
    embedding = fields.Binary(
        string="Vector Embedding",
        attachment=False,
        help="Vector embedding for similarity search",
    )
    embedding_date = fields.Datetime(
        string="Embedding Date",
        readonly=True,
        default=fields.Datetime.now,
    )

    _sql_constraints = [
        (
            "unique_chunk_collection",
            "UNIQUE(chunk_id, collection_id)",
            "A chunk can only have one embedding per collection",
        ),
    ]

    @api.model
    def create_or_update(self, chunk_id, collection_id, embedding_model_id, embedding_data):
        """Create or update embedding for a chunk in a collection"""
        existing = self.search([
            ('chunk_id', '=', chunk_id),
            ('collection_id', '=', collection_id),
        ], limit=1)

        if existing:
            existing.write({
                'embedding_model_id': embedding_model_id,
                'embedding': embedding_data,
                'embedding_date': fields.Datetime.now(),
            })
            return existing
        else:
            return self.create({
                'chunk_id': chunk_id,
                'collection_id': collection_id,
                'embedding_model_id': embedding_model_id,
                'embedding': embedding_data,
            })