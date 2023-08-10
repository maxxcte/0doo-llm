import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class RAGSearchWizard(models.TransientModel):
    _name = "llm.rag.search.wizard"
    _description = "RAG Search Wizard"
    _inherit = ["llm.document.search.mixin"]

    # Search Fields
    query = fields.Text(
        string="Search Query",
        required=True,
        help="Enter your search query here",
    )
    top_k = fields.Integer(
        string="Max Results per Document",
        default=5,
        help="Maximum number of chunks to retrieve per document",
    )
    top_n = fields.Integer(
        string="Max Documents",
        default=3,
        help="Maximum number of documents to retrieve",
    )
    similarity_cutoff = fields.Float(
        string="Similarity Cutoff",
        default=0.5,
        help="Minimum similarity score (0-1) for results",
    )
    collection_id = fields.Many2one(
        "llm.document.collection",
        string="Collection",
        required=True,
        help="Collection to search within",
    )
    search_method = fields.Selection([
        ('semantic', 'Semantic Search'),
        ('hybrid', 'Hybrid Search'),
    ], string="Search Method", default='semantic', required=True)
    state = fields.Selection(
        [("search", "Search"), ("results", "Results")],
        default="search",
        required=True,
    )

    # Results Fields
    result_chunk_ids = fields.Many2many(
        "llm.document.chunk",
        string="Result Chunks",
        readonly=True,
    )
    result_similarity_scores = fields.Json(
        string="Similarity Scores",
        readonly=True,
        help="JSON dictionary mapping chunk IDs to similarity scores",
    )

    # Computed Fields
    result_count = fields.Integer(
        compute="_compute_result_count",
        string="Result Count",
    )

    @api.depends("result_chunk_ids")
    def _compute_result_count(self):
        for wizard in self:
            wizard.result_count = len(wizard.result_chunk_ids)

    @api.model
    def default_get(self, fields_list):
        """Set default collection if available"""
        res = super().default_get(fields_list)

        # Set default collection if there's only one
        if "collection_id" in fields_list and "collection_id" not in res:
            collection = self.env["llm.document.collection"].search(
                [("active", "=", True)], limit=1
            )
            if collection:
                res["collection_id"] = collection.id

        return res

    def _return_wizard(self):
        """Return action to reopen the wizard."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def action_search(self):
        """Execute vector search with the query."""
        self.ensure_one()

        # Get the collection's embedding model
        embedding_model = self.collection_id.embedding_model_id
        if not embedding_model:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Embedding Model"),
                    "message": _("The selected collection has no embedding model configured."),
                    "type": "warning",
                },
            }

        # Get embedding vector for query
        query_vector = embedding_model.embedding(self.query.strip())[0]

        # Set up domain to search only within the selected collection
        domain = [
            ("collection_ids", "=", self.collection_id.id),
        ]

        # If active_ids contains document IDs, further filter chunks by those documents
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids", [])
        if active_model == "llm.document" and active_ids:
            domain.append(("document_id", "in", active_ids))

        # Perform the search using the search mixin
        chunks_with_similarity = self.search_documents(
            query=self.query,
            query_vector=query_vector,
            domain=domain,
            search_method=self.search_method,
            limit=self.top_k * self.top_n,  # Get enough results for processing
            min_similarity=self.similarity_cutoff,
        )

        # Process search results to get top_k chunks from top_n documents
        _, _, selected_chunks = self.process_search_results_base(
            chunks_with_similarity=chunks_with_similarity,
            top_k=self.top_k,
            top_n=self.top_n,
        )

        # Extract chunk records and similarity scores
        result_chunks = self.env["llm.document.chunk"]
        similarity_scores = {}

        for chunk, similarity in selected_chunks:
            result_chunks |= chunk
            similarity_scores[str(chunk.id)] = similarity

        # Update wizard with results
        self.write({
            "state": "results",
            "result_chunk_ids": [(6, 0, result_chunks.ids)],
            "result_similarity_scores": similarity_scores,
        })

        return self._return_wizard()

    def get_similarity_for_chunk(self, chunk_id):
        """Helper method to get similarity score for a chunk from the UI"""
        self.ensure_one()
        if not self.result_similarity_scores:
            return 0.0
        return self.result_similarity_scores.get(str(chunk_id), 0.0)

    def action_back_to_search(self):
        """Reset to search state."""
        self.ensure_one()
        self.write({
            "state": "search",
            "result_chunk_ids": [(5, 0, 0)],
            "result_similarity_scores": {},
        })
        return self._return_wizard()


class RAGSearchResultLine(models.TransientModel):
    _name = "llm.rag.search.result.line"
    _description = "RAG Search Result Line"
    _rec_name = "chunk_id"

    wizard_id = fields.Many2one(
        "llm.rag.search.wizard",
        string="Search Wizard",
        required=True,
        ondelete="cascade",
    )
    chunk_id = fields.Many2one(
        "llm.document.chunk",
        string="Chunk",
        required=True,
    )
    similarity = fields.Float(
        string="Similarity",
        digits=(5, 4),
    )