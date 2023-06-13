import json

import numpy as np

from odoo import api, fields, models

from ..fields.pgvector import PgVector


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

    # Use pgvector field for embeddings
    embedding = PgVector(
        string="Embedding",
        dimensions=1536,  # Default to OpenAI dimensions, configurable later
        help="Vector embedding for this chunk (pgvector format)",
    )

    embedding_model_id = fields.Many2one(
        "llm.model",
        string="Embedding Model",
        related="document_id.embedding_model_id",
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
        "document_id.embedding_model_id",
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
            }

            # Store embedding model info properly
            if record.document_id.embedding_model_id:
                metadata["embedding_model_id"] = (
                    record.document_id.embedding_model_id.id
                )
                metadata["embedding_model_name"] = (
                    record.document_id.embedding_model_id.name
                )

            # Add any additional metadata you might need
            record.metadata = json.dumps(metadata)

    def vector_search(self, query_vector, limit=10):
        """
        Search for similar chunks using vector similarity

        Args:
            query_vector: The query embedding vector (list or numpy array)
            limit: Maximum number of results to return

        Returns:
            Recordset of matching chunks, ordered by similarity
        """
        if not query_vector:
            return self.browse([])

        # Convert to numpy array if it's a list
        if isinstance(query_vector, list):
            query_vector = np.array(query_vector, dtype=np.float32)

        # Format for PostgreSQL vector
        if isinstance(query_vector, np.ndarray):
            pg_vector = f"[{','.join(map(str, query_vector.tolist()))}]"
        else:
            pg_vector = query_vector  # Assume it's already in the right format

        # Register vector with the current cursor
        from pgvector.psycopg2 import register_vector

        register_vector(self.env.cr)

        # Execute raw SQL for vector similarity search
        self.env.cr.execute(
            """
            SELECT id
            FROM llm_document_chunk
            ORDER BY embedding <=> %s
            LIMIT %s
        """,
            (pg_vector, limit),
        )

        chunk_ids = [row[0] for row in self.env.cr.fetchall()]
        return self.browse(chunk_ids)
