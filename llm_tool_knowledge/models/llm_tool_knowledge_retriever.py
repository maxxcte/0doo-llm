import logging
from typing import Any

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolKnowledgeRetriever(models.Model):
    _inherit = "llm.tool"

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("knowledge_retriever", "Knowledge Retriever")]

    @api.model
    def _get_available_collections(self):
        """Retrieve a list of available resource collections.

        Returns:
            list: List of tuples with collection_id and name
        """
        Collection = self.env["llm.knowledge.collection"].sudo()
        collections = Collection.search([("active", "=", True)])
        return [(str(collection.id), collection.name) for collection in collections]

    def knowledge_retriever_execute(
        self,
        query: str,
        collection_id: str,
        top_k: int = 5,
        top_n: int = 3,
        similarity_cutoff: float = 0.5,
    ) -> dict[str, Any]:
        """
        Retrieve relevant knowledge from the resource database using semantic search.

        Use this tool when you need to:
        - Answer questions that require specific information from the knowledge base
        - Find relevant resources or content based on semantic similarity
        - Access information that may not be in your training data

        The tool returns chunks of text from resources ranked by relevance to your query.

        Parameters:
            query: The search query text used to find relevant information. Be specific and focused in your query to get the most relevant results.
            collection_id: The ID (as a string) of the 'llm.knowledge.collection' record to search within. If you don't know the ID, you can use the 'odoo_record_retriever' tool first to search for available collections by name on the 'llm.knowledge.collection' model and get their IDs.
            top_k: Maximum number of chunks to retrieve per resource. Higher values return more context from each resource but may include less relevant passages.
            top_n: Maximum number of distinct resources to retrieve results from. Increase this value to get information from more diverse sources.
            similarity_cutoff: Minimum semantic similarity threshold (0.0-1.0) for including results. Higher values (e.g., 0.7) return only highly relevant results.
        """
        _logger.info(
            f"Executing Knowledge Retriever with: query={query}, collection_id={collection_id}, top_k={top_k}, top_n={top_n}, similarity_cutoff={similarity_cutoff}"
        )

        try:
            # Validate collection exists
            collection = None
            if collection_id:
                collection = self.env["llm.knowledge.collection"].browse(
                    int(collection_id)
                )
                if not collection.exists():
                    _logger.warning(
                        f"Collection with ID {collection_id} not found, falling back to default"
                    )
                    collection = None

            # If no valid collection_id was provided or found, get the default collection
            if not collection:
                # Try to find a default collection (the first active one)
                collection = self.env["llm.knowledge.collection"].search(
                    [("active", "=", True)], limit=1
                )

                if not collection:
                    return {
                        "error": "No valid collection found. Please provide a valid collection ID or set up a default collection."
                    }

                _logger.info(
                    f"Using default collection: {collection.name} (ID: {collection.id})"
                )

            # Get the embedding model from the collection
            embedding_model = collection.embedding_model_id
            if not embedding_model:
                # Fallback to default embedding model if collection doesn't have one
                model_obj = self.env["llm.model"]
                embedding_model = model_obj.search(
                    [("model_use", "=", "embedding"), ("default", "=", True)], limit=1
                )
                if not embedding_model:
                    embedding_model = model_obj.search(
                        [("model_use", "=", "embedding")], limit=1
                    )

            if not embedding_model:
                return {"error": "No embedding model found for this collection"}

            # Get the provider for the embedding model
            provider = embedding_model.provider_id
            if not provider:
                return {"error": f"No provider found for model {embedding_model.name}"}

            # Generate embedding for the query
            query_embedding = provider.embedding([query], model=embedding_model)[0]

            # Prepare domain for resource chunks
            domain = [
                ("collection_ids", "=", collection.id),
            ]

            # Calculate search limit - get more results for better filtering
            search_limit = top_n * top_k * 2

            # Use the direct search method with vector search parameters
            chunk_model = self.env["llm.knowledge.chunk"]
            chunks = chunk_model.search(
                args=domain,
                limit=search_limit,
                query_vector=query_embedding,
                query_min_similarity=similarity_cutoff,
                query_operator="<=>",  # Cosine similarity
            )

            # Process results to get top chunks per resource
            result_data = self._process_search_results(
                chunks=chunks,
                top_k=top_k,
                top_n=top_n,
            )

            return {
                "query": query,
                "collection": collection.name,
                "collection_id": collection.id,
                "results": result_data,
                "total_chunks": len(result_data),
                "embedding_model": embedding_model.name,
            }

        except Exception as e:
            _logger.exception(f"Error executing Knowledge Retriever: {str(e)}")
            return {"error": str(e)}

    def _group_chunks_by_resource(self, chunks):
        """Group chunks by their parent resource."""
        chunks_by_doc = {}
        for chunk in chunks:
            doc_id = chunk.resource_id.id
            if doc_id not in chunks_by_doc:
                chunks_by_doc[doc_id] = []
            chunks_by_doc[doc_id].append(chunk)

        return chunks_by_doc

    def _get_top_resources(self, chunks_by_doc, top_n):
        """Get the top N resources based on their highest similarity chunk."""
        # Get max similarity for each resource
        resource_max_similarity = {}
        for resource_id, resource_chunks in chunks_by_doc.items():
            max_similarity = max(chunk.similarity for chunk in resource_chunks)
            resource_max_similarity[resource_id] = max_similarity

        # Sort resources by max similarity
        return sorted(
            resource_max_similarity.keys(),
            key=lambda resource_id: resource_max_similarity[resource_id],
            reverse=True,
        )[:top_n]

    def _process_search_results(self, chunks, top_k, top_n):
        """Process search results to get the top chunks per resource.

        Args:
            chunks: Recordset of resource chunks with similarity scores in context
            top_k: Number of chunks to retrieve per resource
            top_n: Total number of resources to retrieve

        Returns:
            List of dictionaries with chunk data
        """
        # Group chunks by resource
        chunks_by_doc = self._group_chunks_by_resource(chunks)

        # Sort chunks within each resource by similarity
        for resource_id in chunks_by_doc:
            chunks_by_doc[resource_id].sort(key=lambda chunk: chunk.similarity, reverse=True)
            # Limit to top_k chunks per resource
            chunks_by_doc[resource_id] = chunks_by_doc[resource_id][:top_k]

        # Get top_n resources based on their highest similarity chunk
        top_resources = self._get_top_resources(chunks_by_doc, top_n)

        # Collect selected chunks from top resources
        result_data = []
        for resource_id in top_resources:
            for chunk in chunks_by_doc[resource_id]:
                result_data.append(
                    {
                        "content": chunk.content,
                        "resource_name": chunk.resource_id.name,
                        "resource_id": chunk.resource_id.id,
                        "chunk_id": chunk.id,
                        "chunk_name": chunk.name,
                        "similarity": round(chunk.similarity, 4),
                        "similarity_percentage": f"{int(chunk.similarity * 100)}%",
                    }
                )

        return result_data
