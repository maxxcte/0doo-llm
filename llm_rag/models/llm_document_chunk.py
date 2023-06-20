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

    def vector_search(self, query_vector, limit=10):
        """
        Search for similar chunks using vector similarity

        Args:
            query_vector: The query embedding vector (list or numpy array)
            limit: Maximum number of results to return

        Returns:
            Recordset of matching chunks, ordered by similarity
        """
        _logger = logging.getLogger(__name__)
        
        # Ensure query_vector is in the correct format for pgvector
        if isinstance(query_vector, np.ndarray):
            # Convert numpy array to list
            pg_vector = query_vector.tolist()
        elif isinstance(query_vector, list):
            # Handle nested lists (flatten if needed)
            if query_vector and isinstance(query_vector[0], list):
                # If it's a list of lists, take the first non-empty list
                pg_vector = next((v for v in query_vector if v), query_vector[0])
                if len(query_vector) > 1:
                    _logger.warning(f"Multiple vectors provided ({len(query_vector)}), using first non-empty one")
            else:
                # Already a flat list
                pg_vector = query_vector
        else:
            # Not a list or numpy array
            pg_vector = query_vector

        # Final check to ensure pg_vector is a flat list
        if isinstance(pg_vector, list) and pg_vector and isinstance(pg_vector[0], list):
            _logger.warning("Vector is still nested after processing, flattening to first element")
            pg_vector = pg_vector[0]
            
        # Get a direct connection to the database instead of using self.env.cr
        # This ensures we're using the correct cursor object that pgvector expects
        try:
            # Ensure pg_vector is a list of numbers
            if not isinstance(pg_vector, list):
                _logger.error(f"Vector is not a list: {type(pg_vector)}")
                return self.browse([])
                
            # Check if all elements are numbers
            if not all(isinstance(x, (int, float)) for x in pg_vector):
                _logger.error("Vector contains non-numeric elements")
                return self.browse([])
                
            # Get the database connection from the cursor
            connection = self.env.cr._cnx
            # Register vector with the connection
            from pgvector.psycopg2 import register_vector
            register_vector(connection)
            
            # Format the vector as a string that PostgreSQL can understand
            vector_str = f"[{','.join(str(x) for x in pg_vector)}]"
            
            # Get the IDs of the current recordset to filter the SQL query
            if self.ids:
                # If we have a filtered recordset, only search within those records
                _logger.info(f"Searching within {len(self.ids)} chunks")
                
                # Execute raw SQL for vector similarity search with ID filter
                self.env.cr.execute(
                    """
                    SELECT id
                    FROM llm_document_chunk
                    WHERE id IN %s
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """,
                    (tuple(self.ids), vector_str, limit),
                )
            else:
                # If no filter was applied, search all chunks
                _logger.info("Searching all chunks")
                
                # Execute raw SQL for vector similarity search without filter
                self.env.cr.execute(
                    """
                    SELECT id
                    FROM llm_document_chunk
                    ORDER BY embedding <=> %s::vector
                    LIMIT %s
                """,
                    (vector_str, limit),
                )
            
            chunk_ids = [row[0] for row in self.env.cr.fetchall()]
            return self.browse(chunk_ids)
            
        except Exception as e:
            _logger.error(f"Vector search error: {str(e)}")
            if isinstance(pg_vector, list):
                _logger.error(f"Vector type: {type(pg_vector)}, length: {len(pg_vector)}, sample: {str(pg_vector[:10]) if pg_vector else 'empty'}")
            else:
                _logger.error(f"Vector type: {type(pg_vector)}")
            return self.browse([])
