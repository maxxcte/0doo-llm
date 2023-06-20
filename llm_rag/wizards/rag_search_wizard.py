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
        default=0.7,
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

    # Main Action
    def action_search(self):
        """Execute vector search with the query."""
        self.ensure_one()
        _logger.debug(f"Search query: {self.query}")

        # Get domain from context
        active_ids = self.env.context.get("active_ids", [])

        # Get embedding and vector
        embedding_model = self._get_embedding_model()
        query_vector = self._get_query_vector(embedding_model)

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
            self.write({
                "state": "results",
                "result_ids": [(6, 0, [])],
                "result_lines": [],
            })
            return self._return_wizard()
            
        # Execute vector search using the model's method
        search_limit = self.top_n * self.top_k  # Get more results than needed for filtering
        chunks = chunks_to_search.vector_search(query_vector, limit=search_limit)
        _logger.info(f"Search results: {len(chunks)} chunks")
        # Filter by similarity cutoff
        chunks_with_similarity = []
        for chunk in chunks:
            # Note: vector_search orders by distance, so we need to convert to similarity
            if isinstance(query_vector, np.ndarray):
                try:
                    # Check if embedding attribute exists and has content
                    if hasattr(chunk, 'embedding') and chunk.embedding is not None:
                        # Convert to numpy array safely
                        chunk_vector = np.array(chunk.embedding)
                        _logger.debug(f"Chunk vector shape: {chunk_vector.shape if hasattr(chunk_vector, 'shape') else 'unknown'}")
                        # Verify the array has elements
                        if chunk_vector.size > 0:
                            # Check if dimensions match
                            if chunk_vector.shape != query_vector.shape:
                                _logger.warning(f"Dimension mismatch: query={query_vector.shape}, chunk={chunk_vector.shape}")
                                
                                # Ensure both vectors are 1D for proper comparison
                                if len(query_vector.shape) > 1:
                                    # Flatten the query vector if it's multi-dimensional
                                    query_vector = query_vector.flatten()
                                    _logger.debug(f"Flattened query vector to shape {query_vector.shape}")
                                
                                if len(chunk_vector.shape) > 1:
                                    # Flatten the chunk vector if it's multi-dimensional
                                    chunk_vector = chunk_vector.flatten()
                                    _logger.debug(f"Flattened chunk vector to shape {chunk_vector.shape}")
                                
                                # Final check to ensure sizes match
                                if chunk_vector.size != query_vector.size:
                                    _logger.warning(f"Cannot compare vectors of different sizes: {query_vector.size} vs {chunk_vector.size}")
                                    continue
                                    
                            # Calculate cosine similarity instead of Euclidean distance for better results
                            # Normalize vectors
                            query_norm = np.linalg.norm(query_vector)
                            chunk_norm = np.linalg.norm(chunk_vector)
                            
                            if query_norm > 0 and chunk_norm > 0:
                                # Cosine similarity = dot product of normalized vectors
                                # Ensure vectors are properly aligned for dot product
                                similarity = np.dot(query_vector.flatten(), chunk_vector.flatten()) / (query_norm * chunk_norm)
                                _logger.debug(f"Calculated cosine similarity: {similarity}, cutoff: {self.similarity_cutoff}")
                            else:
                                _logger.warning(f"Zero norm vector detected, using fallback similarity calculation")
                                # Fallback to simple distance calculation
                                similarity = 1 - np.linalg.norm(query_vector - chunk_vector) / (np.linalg.norm(query_vector) + np.linalg.norm(chunk_vector) + 1e-10)
                                _logger.debug(f"Calculated fallback similarity: {similarity}, cutoff: {self.similarity_cutoff}")
                            if similarity >= self.similarity_cutoff:
                                chunks_with_similarity.append((chunk, similarity))
                except Exception as e:
                    _logger.warning(f"Error processing chunk {chunk.id} embedding: {str(e)}")
                    continue

        # Process results
        chunk_ids, result_lines, doc_chunk_count, processed_docs = [], [], {}, set()

        for chunk, similarity in chunks_with_similarity:
            doc_id = chunk.document_id.id
            doc_chunk_count.setdefault(doc_id, 0)

            if doc_id in processed_docs and doc_chunk_count[doc_id] >= self.top_k:
                continue

            chunk_ids.append(chunk.id)
            doc_chunk_count[doc_id] += 1
            result_lines.append(
                (0, 0, {"chunk_id": chunk.id, "similarity": similarity})
            )

            if doc_chunk_count[doc_id] >= self.top_k:
                processed_docs.add(doc_id)

            if len(processed_docs) >= self.top_n and all(
                c >= self.top_k for c in doc_chunk_count.values()
            ):
                break

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
