import logging
from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

class RAGSearchWizard(models.TransientModel):
    _name = "llm.rag.search.wizard"
    _description = "RAG Search Wizard"

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

    def _get_embedding_model(self):
        """Retrieve an embedding model or raise an error."""
        model = self.env["llm.model"].search([("model_use", "=", "embedding")], limit=1)
        if not model:
            self._raise_error(
                "No Embedding Model", "Please configure an embedding model."
            )
        return model

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
        chunk_ids, result_lines = [], []
        doc_chunk_count, processed_docs = {}, set()

        # Sort results by similarity score (descending)
        chunks_with_similarity.sort(key=lambda x: x[1], reverse=True)

        for chunk, similarity in chunks_with_similarity:
            doc_id = chunk.document_id.id
            doc_chunk_count.setdefault(doc_id, 0)

            # Skip if we already have enough chunks for this document
            if doc_id in processed_docs and doc_chunk_count[doc_id] >= self.top_k:
                continue

            # Add this chunk to results
            chunk_ids.append(chunk.id)
            doc_chunk_count[doc_id] += 1
            result_lines.append(
                (0, 0, {"chunk_id": chunk.id, "similarity": similarity})
            )

            # Mark document as processed if we have enough chunks
            if doc_chunk_count[doc_id] >= self.top_k:
                processed_docs.add(doc_id)

            # Stop if we have enough documents with enough chunks each
            if len(processed_docs) >= self.top_n and all(
                    c >= self.top_k for c in doc_chunk_count.values()
            ):
                break

        return chunk_ids, result_lines

    def action_search(self):
        """Execute vector search with the query."""
        self.ensure_one()

        # Get domain from context
        active_ids = self.env.context.get("active_ids", [])

        # Get embedding and vector
        embedding_model = self._get_embedding_model()
        query_vector = embedding_model.embedding(self.query.strip())

        # Get all chunks or filter by documents if active_ids is provided
        chunk_model = self.env["llm.document.chunk"]
        domain = []

        # If active_ids contains document IDs, filter chunks by those documents
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
            return self._return_wizard()

        # Execute semantic search using vector similarity
        search_limit = self.top_n * self.top_k

        # Decide which search method to use
        if self.search_method == "semantic":
            # Use the search_similar method from EmbeddingMixin
            chunks, similarities = chunk_model.search_similar(
                query_vector=query_vector,
                domain=domain,
                limit=search_limit,
                min_similarity=self.similarity_cutoff
            )
            chunks_with_similarity = list(zip(chunks, similarities))
        else:  # hybrid search
            # For hybrid search, combine vector search with keyword search
            # This is a simplified implementation
            semantic_chunks, semantic_similarities = chunk_model.search_similar(
                query_vector=query_vector,
                domain=domain,
                limit=search_limit // 2,  # Half from semantic
                min_similarity=self.similarity_cutoff / 2  # Lower threshold for hybrid
            )

            # Simple keyword search
            keywords = self.query.strip().split()
            keyword_domain = domain.copy()
            for keyword in keywords:
                keyword_domain.append(('content', 'ilike', keyword))

            keyword_chunks = chunk_model.search(keyword_domain, limit=search_limit // 2)

            # Combine results (with dummy similarity for keyword results)
            chunks_with_similarity = list(zip(semantic_chunks, semantic_similarities))
            for chunk in keyword_chunks:
                if chunk not in semantic_chunks:
                    chunks_with_similarity.append((chunk, 0.5))  # Default similarity

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
    similarity = fields.Float(digits=(5, 4), readonly=True)
    similarity_percentage = fields.Char(compute="_compute_similarity_percentage")

    @api.depends("similarity")
    def _compute_similarity_percentage(self):
        for line in self:
            line.similarity_percentage = f"{line.similarity * 100:.2f}%"