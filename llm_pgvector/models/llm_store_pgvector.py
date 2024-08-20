import logging
import numpy as np
from pgvector import Vector
from pgvector.psycopg2 import register_vector

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMStorePgVector(models.Model):
    _inherit = "llm.store"
    _description = "PgVector Store Implementation"

    store_type = fields.Selection(
        selection_add=[("pgvector", "PgVector")],
        ondelete={"pgvector": "set default"},
    )

    # PgVector specific configuration options
    pgvector_index_method = fields.Selection(
        [
            ("ivfflat", "IVFFlat (faster search)"),
            ("hnsw", "HNSW (balanced)"),
        ],
        string="Index Method",
        default="ivfflat",
        help="The index method to use for vector search"
    )

    # -------------------------------------------------------------------------
    # Store Interface Implementation
    # -------------------------------------------------------------------------

    def collection_exists(self, collection_id):
        """Check if a collection exists - for pgvector, collections always 'exist'"""
        self.ensure_one()
        if self.store_type != "pgvector":
            return super().collection_exists(collection_id)

        # For pgvector, we always return True as we're using the existing Odoo tables
        # and not creating separate collections
        return True

    def create_collection(self, collection_id):
        """Create a collection - for pgvector, this is a no-op"""
        self.ensure_one()
        if self.store_type != "pgvector":
            return super().create_collection(collection_id)

        # For pgvector, creating a collection is essentially a no-op
        # since we're using the existing Odoo tables
        collection = self.env['llm.knowledge.collection'].browse(collection_id)
        if not collection.exists():
            _logger.warning(f"Collection {collection_id} does not exist")
            return False

        # But we might want to create the index for the embedding model
        if collection.embedding_model_id:
            self.create_vector_index(collection.id, collection.embedding_model_id.id)

        return True

    def delete_collection(self, collection_id):
        """Delete a collection - for pgvector, we just drop indexes"""
        self.ensure_one()
        if self.store_type != "pgvector":
            return super().delete_collection(collection_id)

        # For pgvector, deleting a collection just means dropping its indexes
        # and deleting any chunk embeddings associated with it
        collection = self.env['llm.knowledge.collection'].browse(collection_id)
        if not collection.exists():
            return True

        # Drop any vector indexes for this collection
        self.drop_vector_index(collection_id, collection.embedding_model_id.id if collection.embedding_model_id else None)

        # Delete all embeddings for this collection
        self.env['llm.knowledge.chunk.embedding'].search([
            ('collection_id', '=', collection_id)
        ]).unlink()

        return True

    def insert_vectors(self, collection_id, vectors, metadatas=None, ids=None):
        """Insert vectors into collection"""
        self.ensure_one()
        if self.store_type != "pgvector":
            return super().insert_vectors(collection_id, vectors, metadatas, ids)

        # Check parameters
        if not ids or len(ids) != len(vectors):
            raise UserError(_("Must provide chunk IDs matching the vectors"))

        if metadatas is None:
            metadatas = [{}] * len(vectors)

        # Get the collection
        collection = self.env['llm.knowledge.collection'].browse(collection_id)
        if not collection.exists() or not collection.embedding_model_id:
            return False

        # Get the embedding model
        embedding_model_id = collection.embedding_model_id.id

        # Insert or update embeddings for each chunk
        for i, (chunk_id, vector, metadata) in enumerate(zip(ids, vectors, metadatas)):
            # Find or create the chunk embedding record
            self.env['llm.knowledge.chunk.embedding'].create_or_update(
                chunk_id=chunk_id,
                collection_id=collection_id,
                embedding_model_id=embedding_model_id,
                embedding_data=vector,
            )

        # Make sure the index exists
        self.create_vector_index(collection_id, embedding_model_id)

        return True

    def delete_vectors(self, collection_id, ids):
        """Delete vectors (embeddings) for specified chunk IDs"""
        self.ensure_one()
        if self.store_type != "pgvector":
            return super().delete_vectors(collection_id, ids)

        # Delete embeddings for the specified chunks in this collection
        self.env['llm.knowledge.chunk.embedding'].search([
            ('collection_id', '=', collection_id),
            ('chunk_id', 'in', ids)
        ]).unlink()

        return True

    def search_vectors(self, collection_id, query_vector, limit=10, offset=0, filter_string=None):
        """
        Search for similar vectors in the collection

        Returns:
            list of dicts with 'id', 'score', and 'metadata'
        """
        self.ensure_one()
        if self.store_type != "pgvector":
            return super().search_vectors(collection_id, query_vector, limit, offset, filter_string)

        collection = self.env['llm.knowledge.collection'].browse(collection_id)
        if not collection.exists() or not collection.embedding_model_id:
            return []

        embedding_model_id = collection.embedding_model_id.id

        # Format the query vector using pgvector's Vector class
        register_vector(self.env.cr._cnx)
        vector_str = Vector._to_db(query_vector)

        # Build the query with proper index hints
        index_name = self._get_index_name('llm_knowledge_chunk_embedding', embedding_model_id)
        index_hint = f"/*+ IndexScan(llm_knowledge_chunk_embedding {index_name}) */"

        # Execute the query to find similar vectors
        query = f"""
            WITH query_vector AS (
                SELECT '{vector_str}'::vector AS vec
            )
            SELECT {index_hint} chunk_id, 1 - (embedding <=> query_vector.vec) as score
            FROM llm_knowledge_chunk_embedding, query_vector
            WHERE collection_id = %s
            AND embedding_model_id = %s
            AND embedding IS NOT NULL
            ORDER BY score DESC
            LIMIT %s
            OFFSET %s
        """

        self.env.cr.execute(query, (collection_id, embedding_model_id, limit, offset))
        results = self.env.cr.fetchall()

        # Format results with chunk IDs as the main identifiers
        formatted_results = []
        chunk_ids = []

        for chunk_id, score in results:
            chunk_ids.append(chunk_id)
            formatted_results.append({
                'id': chunk_id,
                'score': score,
                'metadata': {}  # We don't store additional metadata currently
            })

        # Get metadata for the chunks if needed
        if chunk_ids:
            chunks = self.env['llm.knowledge.chunk'].browse(chunk_ids)
            # Add metadata from chunks if needed
            for i, chunk in enumerate(chunks):
                if i < len(formatted_results):
                    formatted_results[i]['metadata'] = {
                        'resource_id': chunk.resource_id.id,
                        'resource_name': chunk.resource_id.name,
                        'sequence': chunk.sequence,
                    }
                    # Add chunk metadata if present
                    if chunk.metadata:
                        formatted_results[i]['metadata'].update(chunk.metadata)

        return formatted_results

    # -------------------------------------------------------------------------
    # Vector Index Management
    # -------------------------------------------------------------------------

    def _get_index_name(self, table_name, embedding_model_id):
        """Generate a consistent index name based on table and embedding model"""
        return f"{table_name}_emb_model_{embedding_model_id}_idx"

    def create_vector_index(self, collection_id, embedding_model_id, dimensions=None, force=False):
        """Create a vector index for the specified collection and embedding model"""
        self.ensure_one()
        if self.store_type != "pgvector":
            return False

        # Get the embedding model to determine dimensions if not provided
        if not dimensions and embedding_model_id:
            embedding_model = self.env['llm.model'].browse(embedding_model_id)
            if embedding_model.exists():
                # Generate a sample embedding to determine dimensions
                sample_embedding = embedding_model.embedding("")[0]
                dimensions = len(sample_embedding) if sample_embedding else None

        cr = self.env.cr
        table_name = "llm_knowledge_chunk_embedding"

        # Register vector with this cursor
        register_vector(cr._cnx)

        # Generate index name
        index_name = self._get_index_name(table_name, embedding_model_id)

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
                return True

        # Determine the dimension specification
        dim_spec = f"({dimensions})" if dimensions else ""

        # Determine index method
        index_method = self.pgvector_index_method or "ivfflat"

        try:
            # Create appropriate index
            if index_method == "ivfflat":
                # Create IVFFlat index
                cr.execute(f"""
                    CREATE INDEX {index_name} ON {table_name}
                    USING ivfflat((embedding::vector{dim_spec}) vector_cosine_ops)
                    WHERE collection_id = %s AND embedding_model_id = %s AND embedding IS NOT NULL
                """, (collection_id, embedding_model_id))
            elif index_method == "hnsw":
                # Try HNSW index if available in pgvector version
                try:
                    cr.execute(f"""
                        CREATE INDEX {index_name} ON {table_name}
                        USING hnsw((embedding::vector{dim_spec}) vector_cosine_ops)
                        WHERE collection_id = %s AND embedding_model_id = %s AND embedding IS NOT NULL
                    """, (collection_id, embedding_model_id))
                except Exception as e:
                    # Fallback to IVFFlat if HNSW is not available
                    _logger.warning(f"HNSW index not supported, falling back to IVFFlat: {str(e)}")
                    cr.execute(f"""
                        CREATE INDEX {index_name} ON {table_name}
                        USING ivfflat((embedding::vector{dim_spec}) vector_cosine_ops)
                        WHERE collection_id = %s AND embedding_model_id = %s AND embedding IS NOT NULL
                    """, (collection_id, embedding_model_id))

            _logger.info(f"Created vector index {index_name} for collection {collection_id}")
            return True
        except Exception as e:
            _logger.error(f"Error creating vector index: {str(e)}")
            return False

    def drop_vector_index(self, collection_id, embedding_model_id=None):
        """Drop vector index for the specified collection and embedding model"""
        self.ensure_one()
        if self.store_type != "pgvector":
            return False

        table_name = "llm_knowledge_chunk_embedding"

        if embedding_model_id:
            # Drop specific index for this model
            index_name = self._get_index_name(table_name, embedding_model_id)
            self.env.cr.execute(f"DROP INDEX IF EXISTS {index_name}")
            _logger.info(f"Dropped vector index {index_name}")
        else:
            # Try to find all indexes for this table related to this collection
            query = """
                SELECT indexname FROM pg_indexes
                WHERE tablename = %s
            """
            self.env.cr.execute(query, (table_name,))
            indexes = self.env.cr.fetchall()

            # Drop each index that seems related to this collection
            # This is a best-effort approach since we can't directly determine which indexes
            # are specifically for this collection based only on the index name
            for index in indexes:
                if "emb_model_" in index[0]:
                    self.env.cr.execute(f"DROP INDEX IF EXISTS {index[0]}")
                    _logger.info(f"Dropped vector index {index[0]}")

        return True