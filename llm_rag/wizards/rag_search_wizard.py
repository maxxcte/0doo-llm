import logging

import numpy as np

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class RAGSearchWizard(models.TransientModel):
    _name = "llm.rag.search.wizard"
    _description = "RAG Search Wizard"

    # Fields
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
    state = fields.Selection(
        [("search", "Search"), ("results", "Results")],
        default="search",
        required=True,
    )
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

    # Helper Methods
    def _get_embedding_model(self):
        """Retrieve an embedding model or raise an error."""
        model = self.env["llm.model"].search([("model_use", "=", "embedding")], limit=1)
        if not model:
            self._raise_error(
                "No Embedding Model", "Please configure an embedding model."
            )
        return model

    def _get_query_vector(self, embedding_model):
        """Generate query embedding vector."""
        try:
            embedding = embedding_model.embedding(self.query.strip())
            return (
                np.array(embedding, dtype=np.float32)
                if isinstance(embedding, list)
                else embedding
            )
        except Exception as e:
            self._raise_error(
                "Embedding Error", f"Failed to generate embedding: {str(e)}"
            )

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

    def _prepare_query_vector(self, query_vector):
        """
        Prepare the query vector for similarity calculations.

        Args:
            query_vector: The raw query vector from the embedding model

        Returns:
            tuple: (flattened_vector, vector_norm)
        """
        if not isinstance(query_vector, np.ndarray):
            return query_vector, None

        # Flatten if needed
        if len(query_vector.shape) > 1:
            query_vector = query_vector.flatten()

        # Calculate norm
        query_norm = np.linalg.norm(query_vector)

        return query_vector, query_norm

    def _prepare_chunk_vector(self, chunk_vector, query_vector_shape):
        """
        Prepare a chunk vector for similarity comparison.

        Args:
            chunk_vector: The chunk's embedding vector
            query_vector_shape: Shape of the query vector to match

        Returns:
            numpy.ndarray or None: Prepared vector or None if incompatible
        """
        # Verify the array has elements
        if chunk_vector.size == 0:
            return None

        # Check if dimensions match
        if chunk_vector.shape != query_vector_shape:
            # Flatten the chunk vector if needed
            if len(chunk_vector.shape) > 1:
                chunk_vector = chunk_vector.flatten()

            # Final check to ensure sizes match
            if chunk_vector.size != query_vector_shape[0]:
                return None

        return chunk_vector

    def _calculate_similarity(self, query_vector, chunk_vector, query_norm=None):
        """
        Calculate similarity between query and chunk vectors.

        Args:
            query_vector: The prepared query vector
            chunk_vector: The prepared chunk vector
            query_norm: Pre-calculated query norm (optional)

        Returns:
            float: Similarity score between 0 and 1
        """
        # Calculate norms
        if query_norm is None:
            query_norm = np.linalg.norm(query_vector)

        chunk_norm = np.linalg.norm(chunk_vector)

        # Calculate similarity
        if query_norm > 0 and chunk_norm > 0:
            # Cosine similarity = dot product of normalized vectors
            return np.dot(query_vector, chunk_vector) / (query_norm * chunk_norm)
        else:
            # Fallback for zero norm vectors
            return 1 - np.linalg.norm(query_vector - chunk_vector) / (
                np.linalg.norm(query_vector) + np.linalg.norm(chunk_vector) + 1e-10
            )

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
        original_query_vector = self._get_query_vector(embedding_model)

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

        # Execute vector search using the model's method
        search_limit = (
            self.top_n * self.top_k
        )  # Get more results than needed for filtering
        chunks = chunks_to_search.vector_search(
            original_query_vector, limit=search_limit
        )

        # Prepare query vector once - outside the loop
        query_vector, query_norm = self._prepare_query_vector(original_query_vector)

        # Filter by similarity cutoff
        chunks_with_similarity = []
        for chunk in chunks:
            try:
                # Check if embedding attribute exists and has content
                if hasattr(chunk, "embedding") and chunk.embedding is not None:
                    # Convert to numpy array safely
                    chunk_vector = np.array(chunk.embedding)

                    # Prepare chunk vector
                    prepared_chunk_vector = self._prepare_chunk_vector(
                        chunk_vector, query_vector.shape
                    )
                    if prepared_chunk_vector is None:
                        continue

                    # Calculate similarity
                    similarity = self._calculate_similarity(
                        query_vector, prepared_chunk_vector, query_norm
                    )

                    # Add to results if above cutoff
                    if similarity >= self.similarity_cutoff:
                        chunks_with_similarity.append((chunk, similarity))
            except Exception as e:
                _logger.warning(
                    f"Error processing chunk {chunk.id} embedding: {str(e)}"
                )
                continue

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
