import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
    # TODO: Is this only for searching?
    embedding = fields.Char(
        string="Embedding",
        compute=None,
        store=False,
    )

    # Virtual field to store similarity score in search results
    similarity = fields.Float(
        string="Similarity Score", store=False, compute="_compute_similarity"
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
        models = self.env["llm.model"]
        for collection in self.collection_ids:
            if collection.embedding_model_id:
                models |= collection.embedding_model_id
        return models

    def unlink(self):
        """Override unlink to remove vectors from vector stores before deleting chunks"""
        # Group chunks by collection for efficient processing
        chunks_by_collection = {}
        for chunk in self:
            for collection in chunk.collection_ids:
                if collection.id not in chunks_by_collection:
                    chunks_by_collection[collection.id] = self.env[
                        "llm.knowledge.chunk"
                    ]
                chunks_by_collection[collection.id] |= chunk

        # Remove vectors from each collection's store
        for collection_id, chunks in chunks_by_collection.items():
            collection = self.env["llm.knowledge.collection"].browse(collection_id)
            if collection.store_id:
                try:
                    collection.delete_vectors(ids=chunks.ids)
                    _logger.info(
                        f"Removed {len(chunks)} vectors from collection {collection.name} (ID: {collection.id})"
                    )
                except Exception as e:
                    _logger.warning(
                        f"Error removing vectors for chunks from collection {collection.name} (ID: {collection.id}): {str(e)}"
                    )

        # Proceed with standard deletion
        return super().unlink()

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False, **kwargs):
        vector_search_term = None
        original_args = list(args)  # Keep original args for potential fallback
        search_args = []  # Args to pass to vector store filter or fallback search
        for arg in args:
            if (
                isinstance(arg, (list, tuple))
                and len(arg) == 3
                and arg[0] == "embedding"
                and isinstance(arg[2], str)
            ):
                vector_search_term = arg[2]
            else:
                search_args.append(arg)

        query_vector = kwargs.get("query_vector")
        specific_collection_id = kwargs.get("collection_id")
        if query_vector and not specific_collection_id:
            raise UserError(
                _(
                    "A pre-computed 'query_vector' can only be used when a specific 'collection_id' is also provided."
                    " Searching across multiple collections requires a 'vector_search_term' for model-specific embedding generation."
                )
            )

        can_vector_search = bool(query_vector or vector_search_term)
        if not can_vector_search:
            return super().search(
                original_args,
                offset=offset,
                limit=limit,
                order=order,
                count=count,
                **kwargs,
            )

        collections = self.env["llm.knowledge.collection"]
        if specific_collection_id:
            collection = self.env["llm.knowledge.collection"].browse(
                specific_collection_id
            )
            if (
                collection.exists()
                and collection.store_id
                and (query_vector or collection.embedding_model_id)
            ):
                collections |= collection
            else:
                return super().search(
                    original_args,
                    offset=offset,
                    limit=limit,
                    order=order,
                    count=count,
                    **kwargs,
                )
        else:
            domain = [
                ("active", "=", True),
                ("store_id", "!=", False),
            ]
            if vector_search_term and not query_vector:
                domain.append(("embedding_model_id", "!=", False))
            collections = self.env["llm.knowledge.collection"].search(domain)

        if not collections:
            return 0 if count else self.browse([])

        model_vector_map = {}
        if vector_search_term and not query_vector:
            embedding_models = collections.mapped("embedding_model_id")
            if not embedding_models:
                return super().search(
                    original_args,
                    offset=offset,
                    limit=limit,
                    order=order,
                    count=count,
                    **kwargs,
                )

            for model in embedding_models:
                try:
                    model_vector_map[model.id] = model.embedding(
                        vector_search_term.strip()
                    )[0]
                except Exception:
                    collections = collections.filtered(
                        lambda c, failed_model_id=model.id: c.embedding_model_id.id
                        != failed_model_id
                    )

        if not collections:
            return super().search(
                original_args,
                offset=offset,
                limit=limit,
                order=order,
                count=count,
                **kwargs,
            )

        return self._vector_search_aggregate(
            collections=collections,
            query_vector=query_vector,
            vector_search_term=vector_search_term,
            model_vector_map=model_vector_map,
            search_args=search_args,
            min_similarity=kwargs.get(
                "query_min_similarity",
                self.env.context.get("search_min_similarity", 0.5),
            ),
            query_operator=kwargs.get(
                "query_operator", self.env.context.get("search_vector_operator", "<=>")
            ),
            offset=offset,
            limit=limit,
            count=count,
        )

    def _vector_search_aggregate(
        self,
        collections,
        query_vector,
        vector_search_term,
        model_vector_map,
        search_args,
        min_similarity,
        query_operator,
        offset,
        limit,
        count,
    ):
        """Performs vector search across collections, aggregates, sorts, and limits."""
        # List of tuples: (score, chunk_id)
        aggregated_results = []

        for collection in collections:
            current_query_vector = query_vector
            if not current_query_vector and vector_search_term:
                current_query_vector = model_vector_map.get(
                    collection.embedding_model_id.id
                )

            if not current_query_vector or not collection.store_id:
                continue

            try:
                results = collection.search_vectors(
                    query_vector=current_query_vector,
                    limit=limit,
                    filter=search_args if search_args else None,
                    query_operator=query_operator,
                    min_similarity=min_similarity,
                    offset=0,
                )
                for result in results:
                    aggregated_results.append(
                        (result.get("score", 0.0), result.get("id"))
                    )
            except Exception as e:
                _logger.error(f"Error searching collection {collection.name}: {e}")
                continue

        if not aggregated_results:
            return 0 if count else self.browse([])

        aggregated_results.sort(key=lambda x: (x[0], -x[1]), reverse=True)

        if count:
            return len(aggregated_results)

        final_results = aggregated_results[offset : offset + limit if limit else None]
        chunk_ids = [res[1] for res in final_results]
        similarities = [res[0] for res in final_results]
        similarity_scores = dict(zip(chunk_ids, similarities))  # noqa: B905
        return self.browse(chunk_ids).with_context(similarity_scores=similarity_scores)
