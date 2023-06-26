import logging
from odoo import api, fields, models
from pgvector.psycopg2 import register_vector
from .fields import PgVector

_logger = logging.getLogger(__name__)


class EmbeddingMixin(models.AbstractModel):
    """
    Mixin for models that use vector embeddings.
    Provides common functionality for vector operations.
    """
    _name = 'llm.embedding.mixin'
    _description = 'Vector Embedding Mixin'
    embedding = PgVector(
        string="Embedding",
        help="Vector embedding for this chunk (pgvector format)",
    )

    def _prepare_vector_for_search(self, query_vector):
        """
        Convert query vector to a flat list format suitable for PostgreSQL.

        Args:
            query_vector: The query embedding vector (list or numpy array)

        Returns:
            A flat list of numeric values
        """
        import numpy as np
        
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
        """Format a vector as a string for PostgreSQL."""
        if isinstance(pg_vector, list):
            return f"[{','.join(str(x) for x in pg_vector)}]"
        elif hasattr(pg_vector, 'tolist'):  # For numpy arrays
            return f"[{','.join(str(x) for x in pg_vector.tolist())}]"
        else:
            return str(pg_vector)
    
    def search_similar(self, query_vector, domain=None, limit=10, min_similarity=0.0):
        """
        Search for similar records using vector similarity.
        
        Args:
            query_vector: The query embedding vector (list or numpy array)
            domain: Additional domain filter (optional)
            limit: Maximum number of results to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            A tuple containing:
            - Recordset of matching records, ordered by similarity
            - List of similarity scores for each record
        """
        self.ensure_one()
        _logger = logging.getLogger(__name__)

        # Prepare and validate the vector
        pg_vector = self._prepare_vector_for_search(query_vector)

        if not self._validate_vector(pg_vector):
            _logger.error("Invalid vector format")
            return self.browse([]), []

        # Format the vector for SQL
        vector_str = self._format_vector_for_sql(pg_vector)

        # Register pgvector with the connection
        connection = self.env.cr._cnx
        register_vector(connection)

        # Determine the table and embedding column
        model_table = self._table
        embedding_column = 'embedding'  # Assuming the column is named 'embedding'

        # Build the domain clause
        domain_clause = ""
        params = [vector_str, min_similarity, limit]

        if domain:
            domain_sql, domain_params = self.env['ir.rule']._where_calc(domain, self._name).query.to_sql()
            if domain_sql:
                domain_clause = f"AND {domain_sql}"
                params = [vector_str, min_similarity] + domain_params + [limit]

        # Execute the search query with cosine similarity calculation
        query = f"""
            SELECT id, 1 - ({embedding_column} <=> %s::vector) as similarity
            FROM {model_table}
            WHERE {embedding_column} IS NOT NULL
            AND (1 - ({embedding_column} <=> %s::vector)) >= %s
            {domain_clause}
            ORDER BY similarity DESC
            LIMIT %s
        """

        self.env.cr.execute(query, params)
        results = self.env.cr.fetchall()

        if not results:
            return self.browse([]), []

        # Extract record IDs and similarity scores
        record_ids = [row[0] for row in results]
        similarities = [row[1] for row in results]

        # Return the matching records and their similarity scores
        return self.browse(record_ids), similarities
