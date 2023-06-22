import json
import logging

import numpy as np

from odoo import api, fields, models

from ..fields.pgvector import PgVector

_logger = logging.getLogger(__name__)


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

    def _prepare_vector_for_search(self, query_vector):
        """
        Convert query vector to a flat list format suitable for PostgreSQL.

        Args:
            query_vector: The query embedding vector (list or numpy array)

        Returns:
            A flat list of numeric values
        """
        # Convert numpy array to list
        if isinstance(query_vector, np.ndarray):
            pg_vector = query_vector.tolist()
        # Handle nested lists
        elif isinstance(query_vector, list):
            if query_vector and isinstance(query_vector[0], list):
                # If it's a list of lists, take the first non-empty list
                pg_vector = next((v for v in query_vector if v), query_vector[0])
            else:
                # Already a flat list
                pg_vector = query_vector
        else:
            # Not a list or numpy array
            pg_vector = query_vector

        # Final check to ensure pg_vector is a flat list
        if isinstance(pg_vector, list) and pg_vector and isinstance(pg_vector[0], list):
            pg_vector = pg_vector[0]

        return pg_vector

    def _validate_vector(self, pg_vector):
        """
        Validate that the vector is in the correct format for PostgreSQL.

        Args:
            pg_vector: The vector to validate

        Returns:
            bool: True if valid, False otherwise
        """
        if not isinstance(pg_vector, list):
            return False

        if not all(isinstance(x, (int, float)) for x in pg_vector):
            return False

        return True

    def _format_vector_for_sql(self, pg_vector):
        """
        Format a vector as a string for PostgreSQL.

        Args:
            pg_vector: The vector to format

        Returns:
            str: Formatted vector string
        """
        return f"[{','.join(str(x) for x in pg_vector)}]"

    def _execute_vector_search_query(self, vector_str, limit, filter_ids=None):
        """
        Execute the vector similarity search query.

        Args:
            vector_str: The formatted vector string
            limit: Maximum number of results
            filter_ids: Optional list of IDs to filter by

        Returns:
            list: List of matching record IDs
        """
        # Register pgvector with the connection
        connection = self.env.cr._cnx
        from pgvector.psycopg2 import register_vector

        register_vector(connection)

        # Build and execute the query
        if filter_ids:
            query = """
                SELECT id
                FROM llm_document_chunk
                WHERE id IN %s
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            params = (tuple(filter_ids), vector_str, limit)
        else:
            query = """
                SELECT id
                FROM llm_document_chunk
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """
            params = (vector_str, limit)

        self.env.cr.execute(query, params)
        return [row[0] for row in self.env.cr.fetchall()]

    def vector_search(self, query_vector, limit=10):
        """
        Search for similar chunks using vector similarity.

        Args:
            query_vector: The query embedding vector (list or numpy array)
            limit: Maximum number of results to return

        Returns:
            Recordset of matching chunks, ordered by similarity
        """
        _logger = logging.getLogger(__name__)

        try:
            # Prepare and validate the vector
            pg_vector = self._prepare_vector_for_search(query_vector)

            if not self._validate_vector(pg_vector):
                _logger.error("Invalid vector format")
                return self.browse([])

            # Format the vector for SQL
            vector_str = self._format_vector_for_sql(pg_vector)

            # Execute the search query
            chunk_ids = self._execute_vector_search_query(
                vector_str, limit, filter_ids=self.ids if self.ids else None
            )

            # Return the matching chunks
            return self.browse(chunk_ids)

        except Exception as e:
            _logger.error(f"Vector search error: {str(e)}")
            return self.browse([])
