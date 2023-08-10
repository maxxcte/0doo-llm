import logging
from pgvector import Vector

from odoo import api, fields, models

from .fields import PgVector

_logger = logging.getLogger(__name__)


class EmbeddingMixin(models.AbstractModel):
    """
    Mixin for models that use vector embeddings.

    This mixin provides functionality for vector search operations and index management.
    """
    _name = "llm.embedding.mixin"
    _description = "Vector Embedding Mixin"

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

    # Virtual field to store similarity score in search results
    similarity = fields.Float(string="Similarity Score", store=False, compute="_compute_similarity")

    # Field to store temporary similarity scores
    _similarity_scores = {}

    def _compute_similarity(self):
        """Compute method for the similarity field."""
        for record in self:
            record.similarity = self._similarity_scores.get(record.id, 0.0)

    @api.model
    def _name_search(self, name, args=None, operator='ilike', limit=100, name_get_uid=None):
        """Override _name_search to support semantic search with a 'search_vector' in context."""
        if self.env.context.get('search_vector'):
            vector_domain = self._vector_domain(
                self.env.context.get('search_vector'),
                self.env.context.get('query_min_similarity', 0.0),
                self.env.context.get('query_operator', '<=>'),
                args
            )
            if vector_domain:
                return self._search(vector_domain, limit=limit, access_rights_uid=name_get_uid)
        return super()._name_search(name, args, operator, limit, name_get_uid)

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False, **kwargs):
        """Search records based on vector similarity when a query vector is provided.

        In addition to standard search parameters, you can provide:

        :param query_vector: The query embedding vector for similarity search
        :param query_operator: The vector similarity operator to use (`<->` for L2 distance,
                              `<=>` for cosine distance, `<#>` for negative inner product)
        :param query_min_similarity: Minimum similarity threshold (0-1)
        :return: Recordset of matching records, ordered by similarity
        """
        # Extract vector search parameters
        query_vector = kwargs.get('query_vector')
        query_operator = kwargs.get('query_operator', '<=>')
        query_min_similarity = kwargs.get('query_min_similarity', 0.0)

        if query_vector is not None:
            # This is a vector similarity search
            vector_domain = self._vector_domain(query_vector, query_min_similarity, query_operator, args)

            # Get results and similarity scores
            results, similarities = self._run_vector_search(
                query_vector,
                domain=args,
                limit=limit,
                offset=offset,
                min_similarity=query_min_similarity,
                operator=query_operator
            )

            # Store similarity scores for access through the similarity field
            self._similarity_scores = dict(zip([r.id for r in results], similarities))

            if count:
                return len(results)

            return results

        # Fall back to standard search
        return super().search(args, offset=offset, limit=limit, order=order, count=count)

    def _vector_domain(self, query_vector, min_similarity=0.0, operator='<=>', base_domain=None):
        """Helper to create a domain for vector search."""
        if not query_vector:
            return base_domain or []

        # Convert the domain to a list if it's not already
        domain = list(base_domain or [])

        # Add a domain item that will be handled specially by _search
        domain.append(('embedding', operator, query_vector))

        if min_similarity > 0:
            # Add similarity threshold
            similarity_domain = ('similarity', '>=', min_similarity)
            domain.append(similarity_domain)

        return domain

    def _run_vector_search(self, query_vector, domain=None, limit=None, offset=0, min_similarity=0.0, operator='<=>'):
        """Perform a vector similarity search.

        :param query_vector: The query embedding vector
        :param domain: Additional domain filter
        :param limit: Maximum number of results to return
        :param offset: Number of results to skip
        :param min_similarity: Minimum similarity threshold (0-1)
        :param operator: Similarity operator to use:
            '<->' for L2 distance (Euclidean)
            '<#>' for inner product
            '<=>' for cosine distance
        :return: A tuple containing:
            - Recordset of matching records, ordered by similarity
            - List of similarity scores for each record
        """
        if not query_vector:
            return self.browse(), []

        # Format the query vector using pgvector's Vector class
        vector_str = Vector._to_db(query_vector)

        # Determine the table and embedding column
        model_table = self._table
        embedding_column = "embedding"

        # Check if we have a collection_id in the domain
        collection_id = None
        if domain and hasattr(self, 'collection_ids'):
            for cond in domain:
                if isinstance(cond, (list, tuple)) and len(cond) == 3 and cond[0] == 'collection_ids' and cond[1] == '=':
                    collection_id = cond[2]
                    break

        # Build the domain clause
        domain_clause = ""
        params = [min_similarity]

        if domain:
            # Correctly calculate the WHERE clause using the model itself
            query_obj = self.sudo()._where_calc(domain)
            tables, where_clause, where_params = query_obj.get_sql()

            # Remove the special vector comparison from where_clause if present
            # (it will be handled specially in the CTE query)
            if where_clause:
                domain_clause = f"AND {where_clause}"
                params = [min_similarity] + where_params

        limit_clause = f"LIMIT {int(limit)}" if limit else ""
        offset_clause = f"OFFSET {int(offset)}" if offset else ""

        # Build index hint if we have a collection_id
        index_hint = ""
        if collection_id and hasattr(self, 'collection_ids'):
            index_name = f"{model_table}_emb_collection_{collection_id}_idx"
            # Add index hint - improves performance by telling PostgreSQL which index to use
            # This is especially helpful when we have multiple collection-specific indices
            index_hint = f"/*+ IndexScan({model_table} {index_name}) */"

        # Execute the search query with selected operator and relevance score
        # Using a WITH clause for clarity
        query = f"""
            WITH query_vector AS (
                SELECT '{vector_str}'::vector AS vec
            )
            SELECT {index_hint} id, 1 - ({embedding_column} {operator} query_vector.vec) as similarity
            FROM {model_table}, query_vector
            WHERE {embedding_column} IS NOT NULL
            AND (1 - ({embedding_column} {operator} query_vector.vec)) >= %s
            {domain_clause}
            ORDER BY similarity DESC
            {limit_clause}
            {offset_clause}
        """

        self.env.cr.execute(query, params)
        results = self.env.cr.fetchall()

        if not results:
            return self.browse(), []

        # Extract record IDs and similarity scores
        record_ids = [row[0] for row in results]
        similarities = [row[1] for row in results]

        # Return the matching records and their similarity scores
        return self.browse(record_ids), similarities

    def create_embedding_index(self, collection_id=None, dimensions=None, force=False):
        """
        Create a vector index for embeddings if it doesn't already exist.

        This method creates a vector index for more efficient similarity searches.
        If the model has a collection_ids field, it will create a collection-specific
        index; otherwise, it creates a general index for all embeddings.

        Args:
            collection_id: Collection identifier to filter the index (optional)
            dimensions: Vector dimensions (optional)
            force: If True, drop existing index and recreate it (default: False)
        """
        cr = self.env.cr
        table_name = self._table

        # Register vector with this cursor
        from pgvector.psycopg2 import register_vector
        register_vector(cr._cnx)

        # Generate appropriate index name based on collection
        if collection_id:
            index_name = f"{table_name}_emb_collection_{collection_id}_idx"
        else:
            index_name = f"{table_name}_embedding_idx"

        # Check if index already exists
        if force:
            # Drop existing index if force is True
            cr.execute(f"DROP INDEX IF EXISTS {index_name}")
        else:
            # Check if index exists
            cr.execute(
                """
                    SELECT 1 FROM pg_indexes
                    WHERE indexname = %s
                """,
                (index_name,),
            )

            # If index already exists, return early
            if cr.fetchone():
                _logger.info(f"Index {index_name} already exists, skipping creation")
                return

        # Determine the dimension specification
        dim_spec = f"({dimensions})" if dimensions else ""

        # Create the appropriate index with or without collection filtering
        if collection_id and hasattr(self, 'collection_ids'):
            # For many2many field, we need to create an index based on records that are in the relation table
            relation_table = self.collection_ids._fields['collection_ids'].relation
            record_column = self.collection_ids._fields['collection_ids'].column1
            collection_column = self.collection_ids._fields['collection_ids'].column2

            cr.execute(
                f"""
                    CREATE INDEX {index_name} ON {table_name}
                    USING ivfflat((embedding::vector{dim_spec}) vector_cosine_ops)
                    WHERE id IN (
                        SELECT {record_column} FROM {relation_table}
                        WHERE {collection_column} = %s
                    ) AND embedding IS NOT NULL
                """,
                (collection_id,),
            )
        else:
            # Create general index
            cr.execute(f"""
                    CREATE INDEX IF NOT EXISTS {index_name} ON {table_name}
                    USING ivfflat((embedding::vector{dim_spec}) vector_cosine_ops)
                    WHERE embedding IS NOT NULL
                """)

        _logger.info(f"Created vector index {index_name} on {table_name}.embedding")

    def drop_embedding_index(self, collection_id=None):
        """
        Drop a vector index associated with this model.

        Args:
            collection_id: Collection identifier to determine which index to drop.
                          If None, drops the general index for the model.
        """
        table_name = self._table

        if collection_id:
            index_name = f"{table_name}_emb_collection_{collection_id}_idx"
        else:
            index_name = f"{table_name}_embedding_idx"

        self.env.cr.execute(f"DROP INDEX IF EXISTS {index_name}")
        _logger.info(f"Dropped vector index {index_name}")
