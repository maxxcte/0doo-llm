import logging

from odoo import models

_logger = logging.getLogger(__name__)


class LLMDocumentSearchMixin(models.AbstractModel):
    """Common document search functionality for RAG-related features."""

    _name = "llm.document.search.mixin"
    _description = "Document Search Utilities"

    def perform_semantic_search(self, query_vector, domain, limit, min_similarity):
        """Perform pure semantic search using vector similarity.

        Args:
            query_vector: The embedding vector for the query
            domain: Domain filters for document chunks
            limit: Maximum number of results to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            tuple: (chunks, similarities) - Lists of matching chunks and their similarity scores
        """
        chunk_model = self.env["llm.document.chunk"]
        return chunk_model.search_similar(
            query_vector=query_vector,
            domain=domain,
            limit=limit,
            min_similarity=min_similarity,
        )

    def perform_hybrid_search(self, query, query_vector, domain, limit, min_similarity):
        """Perform hybrid search combining vector similarity with keyword matching.

        Args:
            query: The original text query
            query_vector: The embedding vector for the query
            domain: Domain filters for document chunks
            limit: Maximum number of results to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            list: List of (chunk, similarity) tuples
        """
        chunk_model = self.env["llm.document.chunk"]

        # Semantic search with half the limit and lower threshold
        semantic_chunks, semantic_similarities = chunk_model.search_similar(
            query_vector=query_vector,
            domain=domain,
            limit=limit // 2,
            min_similarity=min_similarity / 2,
        )

        # Keyword search
        keywords = query.strip().split()
        keyword_domain = domain.copy()
        for keyword in keywords:
            keyword_domain.append(("content", "ilike", keyword))

        keyword_chunks = chunk_model.search(keyword_domain, limit=limit // 2)

        # Combine results
        chunks_with_similarity = list(
            zip(semantic_chunks, semantic_similarities)
        )
        for chunk in keyword_chunks:
            if chunk not in semantic_chunks:
                chunks_with_similarity.append((chunk, 0.5))  # Default similarity

        return chunks_with_similarity

    def search_documents(
        self, query, query_vector, domain, search_method, limit, min_similarity
    ):
        """Unified search method that handles both semantic and hybrid search.

        Args:
            query: The original text query
            query_vector: The embedding vector for the query
            domain: Domain filters for document chunks
            search_method: Either "semantic" or "hybrid"
            limit: Maximum number of results to return
            min_similarity: Minimum similarity threshold (0-1)

        Returns:
            list: List of (chunk, similarity) tuples
        """
        if search_method == "semantic":
            chunks, similarities = self.perform_semantic_search(
                query_vector, domain, limit, min_similarity
            )
            return list(zip(chunks, similarities))
        else:  # hybrid search
            return self.perform_hybrid_search(
                query, query_vector, domain, limit, min_similarity
            )

    def group_chunks_by_document(self, chunks_with_similarity):
        """Group chunks by their parent document.

        Args:
            chunks_with_similarity: List of (chunk, similarity) tuples

        Returns:
            dict: Dictionary mapping document IDs to lists of (chunk, similarity) tuples
        """
        chunks_by_doc = {}
        for chunk, similarity in chunks_with_similarity:
            doc_id = chunk.document_id.id
            if doc_id not in chunks_by_doc:
                chunks_by_doc[doc_id] = []
            chunks_by_doc[doc_id].append((chunk, similarity))

        return chunks_by_doc

    def get_top_documents(self, chunks_by_doc, top_n):
        """Get the top N documents based on their highest similarity chunk.

        Args:
            chunks_by_doc: Dictionary mapping document IDs to lists of (chunk, similarity) tuples
            top_n: Number of top documents to return

        Returns:
            list: List of document IDs sorted by maximum similarity
        """
        # Get max similarity for each document
        doc_max_similarity = {
            doc_id: max(chunk_sim[1] for chunk_sim in chunks)
            for doc_id, chunks in chunks_by_doc.items()
        }

        # Sort documents by max similarity
        return sorted(
            doc_max_similarity.keys(),
            key=lambda doc_id: doc_max_similarity[doc_id],
            reverse=True,
        )[:top_n]

    def process_search_results_base(self, chunks_with_similarity, top_k, top_n):
        """Base implementation for processing search results.

        This method handles the common logic of grouping chunks by document,
        sorting by similarity, and selecting the top K chunks from the top N documents.

        Args:
            chunks_with_similarity: List of (chunk, similarity) tuples
            top_k: Number of chunks to retrieve per document
            top_n: Total number of documents to retrieve

        Returns:
            tuple: (chunks_by_doc, top_docs, selected_chunks)
                - chunks_by_doc: Dictionary mapping document IDs to sorted lists of (chunk, similarity) tuples
                - top_docs: List of top document IDs
                - selected_chunks: List of (chunk, similarity) tuples from top documents
        """
        # Group chunks by document
        chunks_by_doc = self.group_chunks_by_document(chunks_with_similarity)

        # Sort chunks within each document by similarity
        for doc_id in chunks_by_doc:
            chunks_by_doc[doc_id].sort(key=lambda x: x[1], reverse=True)
            # Limit to top_k chunks per document
            chunks_by_doc[doc_id] = chunks_by_doc[doc_id][:top_k]

        # Get top_n documents based on their highest similarity chunk
        top_docs = self.get_top_documents(chunks_by_doc, top_n)

        # Collect selected chunks from top documents
        selected_chunks = []
        for doc_id in top_docs:
            selected_chunks.extend(chunks_by_doc[doc_id])

        return chunks_by_doc, top_docs, selected_chunks
