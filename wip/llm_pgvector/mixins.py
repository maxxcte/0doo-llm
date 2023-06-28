import logging
from odoo import api, fields, models
from pgvector import Vector
from .fields import PgVector

_logger = logging.getLogger(__name__)

class EmbeddingMixin(models.AbstractModel):
    """
    Mixin for models that use vector embeddings.
    Provides common functionality for vector search operations.
    """
    _name = 'llm.embedding.mixin'
    _description = 'Vector Embedding Mixin'

    embedding = PgVector(
        string="Embedding",
        help="Vector embedding for similarity search",
    )

    embedding_model_id = fields.Many2one(
        "llm.model",
        string="Embedding Model",
        domain="[('model_use', '=', 'embedding')]",
        help="The model used to create embeddings",
    )

    @api.model
    def search_similar(self, query_vector, domain=None, limit=10, min_similarity=0.0, operator='<=>'):
        """
        Search for similar records using vector similarity.
        This is implemented as a class method (api.model) to allow searching
        across all records, not just a specific recordset.

        Args:
            query_vector: The query embedding vector (list, numpy array)
            domain: Additional domain filter (optional)
            limit: Maximum number of results to return
            min_similarity: Minimum similarity threshold (0-1)
            operator: Similarity operator to use:
                '<->' for L2 distance (Euclidean)
                '<#>' for inner product
                '<=>' for cosine distance

        Returns:
            A tuple containing:
            - Recordset of matching records, ordered by similarity
            - List of similarity scores for each record
        """
        # Format the query vector using pgvector's Vector class
        vector_str = Vector._to_db(query_vector)

        # Determine the table and embedding column
        model_table = self._table
        embedding_column = 'embedding'

        # Build the domain clause
        domain_clause = ""
        params = [vector_str, min_similarity, limit]

        if domain:
            domain_sql, domain_params = self.env['ir.rule']._where_calc(domain, self._name).query.to_sql()
            if domain_sql:
                domain_clause = f"AND {domain_sql}"
                params = [vector_str, min_similarity] + domain_params + [limit]

        # Execute the search query with selected operator
        query = f"""
            SELECT id, 1 - ({embedding_column} {operator} %s::vector) as similarity
            FROM {model_table}
            WHERE {embedding_column} IS NOT NULL
            AND (1 - ({embedding_column} {operator} %s::vector)) >= %s
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
