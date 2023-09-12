import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LLMDocumentChunk(models.Model):
    _name = "llm.document.chunk"
    _description = "Document Chunk for RAG"
    _inherit = ["llm.embedding.mixin"]
    _order = "sequence, id"

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
        index=True,
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order of the chunk within the document",
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
        "llm.document.collection",
        string="Collections",
    )

    @api.depends("document_id.name", "sequence")
    def _compute_name(self):
        for chunk in self:
            if chunk.document_id and chunk.document_id.name:
                chunk.name = f"{chunk.document_id.name} - Chunk {chunk.sequence}"
            else:
                chunk.name = f"Chunk {chunk.sequence}"

    def open_chunk_detail(self):
        """Open a form view of the chunk for detailed viewing."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "llm.document.chunk",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    @api.model
    def search(self, args, offset=0, limit=None, order=None, count=False, **kwargs):
        if self.env.context.get("search_view_vector_search") and args:
            # Find the search term in the domain
            search_term = None
            for arg in args:
                if (
                    isinstance(arg, list)
                    and len(arg) >= 3
                    and arg[0] in ["name", "content"]
                    and arg[1] in ["ilike", "like"]
                ):
                    search_term = arg[2]
                    break

            if search_term:
                # Get a default collection to use its embedding model
                collection = self.env["llm.document.collection"].search([], limit=1)
                if collection and collection.embedding_model_id:
                    # Get the embedding model from the collection
                    embedding_model = collection.embedding_model_id

                    # Generate embedding for the search term
                    vector = embedding_model.embedding(search_term.strip())[0]

                    # # Add collection filter to the domain
                    # collection_domain = [('collection_ids', '=', collection.id)]

                    # Use the vector search
                    kwargs["query_vector"] = vector
                    kwargs["query_min_similarity"] = 0.5
                    kwargs["query_operator"] = "<=>"

                    # Use the modified domain
                    return super().search(
                        [],
                        offset=offset,
                        limit=limit,
                        order=order,
                        count=count,
                        **kwargs,
                    )

        return super().search(
            args, offset=offset, limit=limit, order=order, count=count, **kwargs
        )
