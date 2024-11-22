import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LLMKnowledgeChunk(models.Model):
    _name = "llm.knowledge.chunk"
    _description = "Document Chunk for RAG"
    _order = "sequence, id"

    name = fields.Char(
        string="Name",
        compute="_compute_name",
        store=True,
    )
    resource_id = fields.Many2one(
        "llm.resource",
        string="Resource",
        required=True,
        ondelete="cascade",
        index=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of the chunk within the resource",
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
    # Related field to resource collections
    collection_ids = fields.Many2many(
        "llm.knowledge.collection",
        string="Collections",
        related="resource_id.collection_ids",
        store=False,
    )
    #TODO: Is this only for searching?
    embedding = fields.Char(
        string='Embedding',
        compute=None,
        store=False,
    )

    # Virtual field to store similarity score in search results
    similarity = fields.Float(
        string="Similarity Score",
        store=False,
        compute="_compute_similarity"
    )

    @api.depends("resource_id.name", "sequence")
    def _compute_name(self):
        for chunk in self:
            if chunk.resource_id and chunk.resource_id.name:
                chunk.name = f"{chunk.resource_id.name} - Chunk {chunk.sequence}"
            else:
                chunk.name = f"Chunk {chunk.sequence}"

    def _compute_similarity(self):
        """Compute method for the similarity field."""
        for record in self:
            # Get the similarity score from the context
            record.similarity = self.env.context.get("similarity_scores", {}).get(
                record.id, 0.0
            )

    def open_chunk_detail(self):
        """Open a form view of the chunk for detailed viewing."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "llm.knowledge.chunk",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def get_collection_embedding_models(self):
        """Helper method to get embedding models for this chunk's collections"""
        self.ensure_one()
        models = self.env['llm.model']
        for collection in self.collection_ids:
            if collection.embedding_model_id:
                models |= collection.embedding_model_id
        return models
    
    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False, **kwargs):
        """
        Extend search to support semantic search via store implementations

        The semantic search can be triggered in two ways:
        1. Via the 'embedding' field in args with a string value
        2. Via a query_vector and collection_id provided directly in kwargs
        """
        # Check if semantic search is requested via the embedding field
        vector_search_term = None
        for arg in args:
            if (
                    isinstance(arg, (list, tuple))
                    and len(arg) == 3
                    and arg[0] == "embedding"
                    and isinstance(arg[2], str)
            ):
                vector_search_term = arg[2]
                args = [a for a in args if a != arg]  # Remove the embedding condition
                break

        # Get query_vector either from kwargs or by converting search term
        query_vector = kwargs.get("query_vector")
        # TODO: Make sure to iterate over all collections and combine results if collection_id is not provided
        collection_id = kwargs.get("collection_id")

        if vector_search_term and not query_vector:
            # Get a default collection to use its embedding model
            collection = collection_id and self.env["llm.knowledge.collection"].browse(collection_id) or \
                         self.env["llm.knowledge.collection"].search([], limit=1)

            if collection and collection.embedding_model_id:
                # Generate the vector using the collection's embedding model
                embedding_model = collection.embedding_model_id
                query_vector = embedding_model.embedding(vector_search_term.strip())[0]
                collection_id = collection.id

        # If we have a query vector and collection, use the store for search
        if query_vector is not None and collection_id:
            collection = self.env["llm.knowledge.collection"].browse(collection_id)
            if collection.exists() and collection.store_id:
                # Get search parameters
                min_similarity = kwargs.get("query_min_similarity",
                                                  self.env.context.get("search_min_similarity", 0.5))
                query_operator = kwargs.get("query_operator", self.env.context.get("search_vector_operator", "<=>"))
                # Use the store's vector search capability
                try:
                    results = collection.search_vectors(
                        query_vector=query_vector,
                        limit=limit,
                        filter=args if args else None,
                        query_operator=query_operator,
                        min_similarity=min_similarity,
                        offset=offset,
                    )

                    if count:
                        return len(results)

                    # Extract chunk IDs and similarity scores
                    chunk_ids = []
                    similarities = []

                    for result in results:
                        chunk_ids.append(result.get('id'))
                        similarities.append(result.get('score', 0.0))

                    # Store similarity scores in context for the virtual field
                    similarity_scores = dict(zip(chunk_ids, similarities))

                    # Return the found chunks with similarity scores in context
                    return self.browse(chunk_ids).with_context(similarity_scores=similarity_scores)
                except Exception as e:
                    _logger.error(f"Error in vector search: {str(e)}")
                    # Fall back to standard search

        # Fallback to standard search if vector search is not possible
        return super().search(args, offset=offset, limit=limit, order=order, count=count, **kwargs)
