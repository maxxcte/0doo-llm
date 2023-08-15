import logging
import json

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

    def _perform_semantic_search(self, query_vector, domain, limit):
        """Perform semantic search using vector similarity."""
        chunk_model = self.env["llm.document.chunk"]

        # Use the vector search from EmbeddingMixin
        return chunk_model.search(
            args=domain,
            limit=limit,
            query_vector=query_vector,
            query_min_similarity=self.similarity_cutoff,
            query_operator="<=>"  # Cosine similarity
        )

    def _perform_hybrid_search(self, query, query_vector, domain, limit):
        """Perform hybrid search combining vector similarity with keyword matching."""
        chunk_model = self.env["llm.document.chunk"]

        # Semantic search with half the limit and lower threshold
        semantic_chunks = chunk_model.search(
            args=domain,
            limit=limit // 2,
            query_vector=query_vector,
            query_min_similarity=self.similarity_cutoff / 2,
            query_operator="<=>"  # Cosine similarity
        )

        semantic_chunk_ids = semantic_chunks.ids

        # Keyword search
        keywords = query.strip().split()
        keyword_domain = domain.copy()
        for keyword in keywords:
            keyword_domain.append(("content", "ilike", keyword))

        keyword_chunks = chunk_model.search(keyword_domain, limit=limit // 2)

        # Combine results, prioritizing semantic results
        combined_chunks = semantic_chunks

        # Add keyword results that weren't in semantic results
        for chunk in keyword_chunks:
            if chunk.id not in semantic_chunk_ids:
                combined_chunks |= chunk

        return combined_chunks

    def _group_chunks_by_document(self, chunks):
        """Group chunks by their parent document."""
        chunks_by_doc = {}
        for chunk in chunks:
            doc_id = chunk.document_id.id
            if doc_id not in chunks_by_doc:
                chunks_by_doc[doc_id] = []
            chunks_by_doc[doc_id].append(chunk)

        return chunks_by_doc

    def _get_top_documents(self, chunks_by_doc, top_n):
        """Get the top N documents based on their highest similarity chunk."""
        # Get max similarity for each document
        doc_max_similarity = {}
        for doc_id, doc_chunks in chunks_by_doc.items():
            max_similarity = max(chunk.similarity for chunk in doc_chunks)
            doc_max_similarity[doc_id] = max_similarity

        # Sort documents by max similarity
        return sorted(
            doc_max_similarity.keys(),
            key=lambda doc_id: doc_max_similarity[doc_id],
            reverse=True,
        )[:top_n]

    def _process_search_results(self, chunks, top_k, top_n):
        """Process search results into format needed by the UI."""
        # Group chunks by document
        chunks_by_doc = self._group_chunks_by_document(chunks)

        # Sort chunks within each document by similarity
        for doc_id in chunks_by_doc:
            chunks_by_doc[doc_id].sort(key=lambda chunk: chunk.similarity, reverse=True)
            # Limit to top_k chunks per document
            chunks_by_doc[doc_id] = chunks_by_doc[doc_id][:top_k]

        # Get top_n documents based on their highest similarity chunk
        top_docs = self._get_top_documents(chunks_by_doc, top_n)

        # Collect selected chunks from top documents
        selected_chunks = self.env["llm.document.chunk"]
        for doc_id in top_docs:
            selected_chunks |= self.env["llm.document.chunk"].browse([c.id for c in chunks_by_doc[doc_id]])

        # Extract similarity scores for UI display
        similarity_scores = {}
        for chunk in selected_chunks:
            similarity_scores[str(chunk.id)] = chunk.similarity

        return selected_chunks, similarity_scores

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

        # Perform the search based on selected method
        search_limit = self.top_k * self.top_n * 2  # Get more results for better filtering

        if self.search_method == 'semantic':
            chunks = self._perform_semantic_search(query_vector, domain, search_limit)
        else:  # hybrid search
            chunks = self._perform_hybrid_search(self.query, query_vector, domain, search_limit)

        # Process search results to get top_k chunks from top_n documents
        result_chunks, similarity_scores = self._process_search_results(
            chunks=chunks,
            top_k=self.top_k,
            top_n=self.top_n,
        )

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
