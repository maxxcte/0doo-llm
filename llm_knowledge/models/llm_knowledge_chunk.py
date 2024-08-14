import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LLMKnowledgeChunk(models.Model):
    _name = "llm.knowledge.chunk"
    _description = "Document Chunk for RAG"
    _inherit = ["llm.embedding.mixin"]
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
    # Simple collection_ids field as shown in the README
    collection_ids = fields.Many2many(
        "llm.knowledge.collection",
        string="Collections",
        related="resource_id.collection_ids",
        store=False,
    )

    @api.depends("resource_id.name", "sequence")
    def _compute_name(self):
        for chunk in self:
            if chunk.resource_id and chunk.resource_id.name:
                chunk.name = f"{chunk.resource_id.name} - Chunk {chunk.sequence}"
            else:
                chunk.name = f"Chunk {chunk.sequence}"

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

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False, **kwargs):
        # Check if vector search is implicitly requested via the 'embedding' field
        vector_search_term = None

        for arg in args:
            if (
                isinstance(arg, (list, tuple))
                and len(arg) == 3
                and arg[0] == "embedding"
                # Trigger vector search if any operator is used with a string value
                and isinstance(arg[2], str)  # Expecting a search term string
            ):
                vector_search_term = arg[2]
                break  # Found our vector search term, no need to continue

        if vector_search_term:
            # Get a default collection to use its embedding model
            collection = self.env["llm.knowledge.collection"].search([], limit=1)
            if collection and collection.embedding_model_id:
                embedding_model = collection.embedding_model_id
                vector = embedding_model.embedding(vector_search_term.strip())[0]

                kwargs["query_vector"] = vector
                # Get similarity threshold from context or use default
                similarity_threshold = self.env.context.get(
                    "search_similarity_threshold", 0.5
                )
                kwargs["query_min_similarity"] = similarity_threshold
                # Get vector operator from context or use default cosine similarity
                vector_operator = self.env.context.get("search_vector_operator", "<=>")
                kwargs["query_operator"] = vector_operator

                return super().search(
                    [],  # Empty domain - rely solely on vector similarity, as other domain conditions are irrelevant
                    offset=offset,
                    limit=limit,
                    order=order,
                    count=count,
                    **kwargs,
                )
            else:
                # Fallback or raise error if no embedding model found?
                # For now, fallback to standard search without vector enhancement
                _logger.warning(
                    "Vector search requested on 'embedding' field, but no default embedding model found."
                )
                # Call super with the original args (including the embedding condition)
                # This might fail if the ORM doesn't understand the operator for PgVector.
                return super().search(
                    args, offset=offset, limit=limit, order=order, count=count, **kwargs
                )

        # If no vector search condition on 'embedding' field, proceed as normal
        return super().search(
            args, offset=offset, limit=limit, order=order, count=count, **kwargs
        )
