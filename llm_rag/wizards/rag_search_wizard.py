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
        string="Top K Chunks",
        default=5,
        help="Number of chunks to retrieve per document",
    )
    top_n = fields.Integer(
        string="Top N Documents",
        default=3,
        help="Total number of documents to retrieve",
    )
    similarity_cutoff = fields.Float(
        string="Similarity Cutoff",
        default=0.5,
        help="Minimum similarity score (0-1) for results",
    )
    search_method = fields.Selection(
        [
            ("semantic", "Semantic Search"),
            ("hybrid", "Hybrid Search"),
        ],
        string="Search Method",
        default="semantic",
        help="Method to use for searching documents",
    )
    collection_id = fields.Many2one(
        "llm.document.collection",
        string="Collection",
        required=True,
        help="Collection to search within",
    )
    state = fields.Selection(
        [("search", "Search"), ("results", "Results")],
        default="search",
        required=True,
    )

    # Results Fields
    result_ids = fields.Many2many(
        "llm.document.chunk",
        string="Search Results",
        readonly=True,
    )
    result_lines = fields.One2many(
        "llm.rag.search.result.line",
        "wizard_id",
        string="Result Lines",
    )

    # Computed Fields
    result_count = fields.Integer(
        compute="_compute_result_count",
        string="Result Count",
    )

    @api.depends("result_ids")
    def _compute_result_count(self):
        for wizard in self:
            wizard.result_count = len(wizard.result_ids)

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

    def _raise_error(self, title, message, message_type="warning"):
        """Raise a user-friendly error notification."""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _(title),
                "message": _(message),
                "type": message_type,
                "sticky": False,
            },
        }

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

    def _process_search_results(self, chunks_with_similarity):
        """
        Process search results to get the top chunks per document.

        Args:
            chunks_with_similarity: List of (chunk, similarity) tuples

        Returns:
            tuple: (chunk_ids, result_lines) for wizard update
        """
        # Use the inherited mixin methods directly
        _, _, selected_chunks = self.process_search_results_base(
            chunks_with_similarity, self.top_k, self.top_n
        )

        # Convert to the format needed for the wizard
        chunk_ids = []
        result_lines = []

        for chunk, similarity in selected_chunks:
            chunk_ids.append(chunk.id)
            result_lines.append(
                (0, 0, {"chunk_id": chunk.id, "similarity": similarity})
            )

        return chunk_ids, result_lines

    def action_search(self):
        """Execute vector search with the query."""
        self.ensure_one()

        # Make sure collection is selected
        if not self.collection_id:
            return self._raise_error(
                "No Collection Selected",
                "Please select a collection to search within.",
            )

        # Get the collection's embedding model
        embedding_model = self.collection_id.embedding_model_id
        if not embedding_model:
            return self._raise_error(
                "No Embedding Model",
                "The selected collection has no embedding model configured.",
            )

        # Get embedding vector for query
        query_vector = embedding_model.embedding(self.query.strip())[0]

        # Set up domain to search only within the selected collection
        chunk_model = self.env["llm.document.chunk"]
        domain = [
            ("document_id", "in", self.collection_id.document_ids.ids),
        ]

        # If active_ids contains document IDs, further filter chunks by those documents
        active_ids = self.env.context.get("active_ids", [])
        if active_ids:
            domain.append(("document_id", "in", active_ids))

        # Get all chunks matching the domain
        chunks_to_search = chunk_model.search(domain)

        # If no chunks found, return empty results
        if not chunks_to_search:
            self.write(
                {
                    "state": "results",
                    "result_ids": [(6, 0, [])],
                    "result_lines": [],
                }
            )
            _logger.info(
                f"No chunks found for collection {self.collection_id.name} with domain {domain}"
            )
            return self._return_wizard()

        # Execute semantic search using vector similarity
        search_limit = self.top_n * self.top_k

        # Use the inherited mixin methods directly
        chunks_with_similarity = self.search_documents(
            query=self.query.strip(),
            query_vector=query_vector,
            domain=domain,
            search_method=self.search_method,
            limit=search_limit,
            min_similarity=self.similarity_cutoff,
        )

        # Process results to get top chunks per document
        chunk_ids, result_lines = self._process_search_results(chunks_with_similarity)

        # Update wizard
        self.write(
            {
                "state": "results",
                "result_ids": [(6, 0, chunk_ids)],
                "result_lines": result_lines,
            }
        )
        return self._return_wizard()

    def action_back_to_search(self):
        """Reset to search state."""
        self.ensure_one()
        self.write(
            {"state": "search", "result_ids": [(5, 0, 0)], "result_lines": [(5, 0, 0)]}
        )
        return self._return_wizard()


class RAGSearchResultLine(models.TransientModel):
    _name = "llm.rag.search.result.line"
    _description = "RAG Search Result Line"
    _order = "similarity desc"

    wizard_id = fields.Many2one(
        "llm.rag.search.wizard", required=True, ondelete="cascade"
    )
    chunk_id = fields.Many2one("llm.document.chunk", required=True, readonly=True)
    document_id = fields.Many2one(
        related="chunk_id.document_id", store=True, readonly=True
    )
    document_name = fields.Char(related="document_id.name", readonly=True)
    chunk_name = fields.Char(related="chunk_id.name", readonly=True)
    content = fields.Text(related="chunk_id.content", readonly=True)
    collection_id = fields.Many2one(
        related="wizard_id.collection_id",
        string="Collection",
        readonly=True,
    )
    similarity = fields.Float(digits=(5, 4), readonly=True)
    similarity_percentage = fields.Char(compute="_compute_similarity_percentage")

    @api.depends("similarity")
    def _compute_similarity_percentage(self):
        for line in self:
            line.similarity_percentage = f"{line.similarity * 100:.2f}%"
