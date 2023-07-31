import logging

from pydantic import BaseModel, ConfigDict, Field

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolKnowledgeRetriever(models.Model):
    _name = "llm.tool"
    _inherit = ["llm.tool", "llm.document.search.mixin"]

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("knowledge_retriever", "Knowledge Retriever")]

    @api.model
    def _get_available_collections(self):
        """Retrieve a list of available document collections.

        Returns:
            list: List of tuples with collection_id and name
        """
        Collection = self.env['llm.document.collection'].sudo()
        collections = Collection.search([('active', '=', True)])
        return [(str(collection.id), collection.name) for collection in collections]

    def knowledge_retriever_get_pydantic_model(self):
        """Define the Pydantic model for knowledge retriever parameters"""

        # Get available collections for the dropdown field
        available_collections = self._get_available_collections()
        collections_description = ", ".join([f"'{name}' (ID: {collection_id})" for collection_id, name in available_collections])

        class KnowledgeRetrieverParams(BaseModel):
            """This tool retrieves relevant knowledge from the document database using semantic search.

            Use this tool when you need to:
            - Answer questions that require specific information from the knowledge base
            - Find relevant documents or content based on semantic similarity
            - Access information that may not be in your training data

            The tool returns chunks of text from documents ranked by relevance to your query.
            """

            model_config = ConfigDict(
                title=self.name or "knowledge_retriever",
            )

            query: str = Field(
                ...,
                description="The search query text used to find relevant information. Be specific and focused in your query to get the most relevant results.",
            )

            collection_id: str = Field(
                ...,
                description=f"ID of the document collection to search. Available collections: {collections_description}. This determines which set of documents will be searched.",
                enum=[collection_id for collection_id, _ in available_collections],
            )
            top_k: int = Field(
                5,
                description="Maximum number of chunks to retrieve per document. Higher values return more context from each document but may include less relevant passages.",
            )
            top_n: int = Field(
                3,
                description="Maximum number of distinct documents to retrieve results from. Increase this value to get information from more diverse sources.",
            )
            similarity_cutoff: float = Field(
                0.5,
                description="Minimum semantic similarity threshold (0.0-1.0) for including results. Higher values (e.g., 0.7) return only highly relevant results, while lower values (e.g., 0.3) return more results but may include less relevant ones.",
            )
            search_method: str = Field(
                "semantic",
                description="Search method to use: 'semantic' (vector similarity only) or 'hybrid' (combines vector search with keyword matching). Use 'hybrid' when looking for specific terms or when semantic search alone doesn't yield good results.",
                enum=["semantic", "hybrid"],
            )

        return KnowledgeRetrieverParams

    def knowledge_retriever_execute(self, parameters):
        """Execute the knowledge retriever tool"""
        _logger.info(f"Executing Knowledge Retriever with parameters: {parameters}")

        # Extract parameters
        query = parameters.get("query")
        collection_id = parameters.get("collection_id")
        embedding_model_id = parameters.get("embedding_model_id")
        top_k = parameters.get("top_k", 5)
        top_n = parameters.get("top_n", 3)
        similarity_cutoff = parameters.get("similarity_cutoff", 0.5)
        search_method = parameters.get("search_method", "semantic")

        if not query:
            return {"error": "Query is required"}

        if not collection_id:
            return {"error": "Collection ID is required"}

        try:
            # Validate collection exists
            collection = self.env['llm.document.collection'].browse(int(collection_id))
            if not collection.exists():
                return {"error": f"Collection with ID {collection_id} not found"}

            # Get the embedding model
            model_obj = self.env["llm.model"]

            if embedding_model_id:
                embedding_model = model_obj.browse(embedding_model_id)
                if not embedding_model.exists():
                    return {
                        "error": f"Embedding model with ID {embedding_model_id} not found"
                    }
                if embedding_model.model_use != "embedding":
                    return {
                        "error": f"Model {embedding_model.name} (ID: {embedding_model_id}) is not an embedding model. Selected model must have model_use = 'embedding'."
                    }
            else:
                # Get default embedding model
                embedding_model = model_obj.search(
                    [("model_use", "=", "embedding"), ("default", "=", True)], limit=1
                )
                if not embedding_model:
                    embedding_model = model_obj.search(
                        [("model_use", "=", "embedding")], limit=1
                    )

            if not embedding_model:
                return {"error": "No embedding model found"}

            # Get the provider for the embedding model
            provider = embedding_model.provider_id
            if not provider:
                return {"error": f"No provider found for model {embedding_model.name}"}

            # Generate embedding for the query
            query_embedding = provider.embedding([query], model=embedding_model)[0]

            # Prepare domain for document chunks
            domain = [
                ("embedding_model_id", "=", embedding_model.id),
                ("embedding", "!=", False),
                ("document_id.collection_ids", "=", int(collection_id)),
            ]

            # Calculate search limit
            search_limit = top_n * top_k

            # Use the inherited mixin methods directly
            chunks_with_similarity = self.search_documents(
                query=query,
                query_vector=query_embedding,
                domain=domain,
                search_method=search_method,
                limit=search_limit,
                min_similarity=similarity_cutoff,
            )

            # Process results to get top chunks per document
            result_data = self._process_search_results(
                chunks_with_similarity, top_k, top_n
            )

            return {
                "query": query,
                "collection": collection.name,
                "results": result_data,
                "total_chunks": len(result_data),
                "embedding_model": embedding_model.name,
                "search_method": search_method,
            }

        except Exception as e:
            _logger.exception(f"Error executing Knowledge Retriever: {str(e)}")
            return {"error": str(e)}

    def _process_search_results(self, chunks_with_similarity, top_k, top_n):
        """Process search results to get the top chunks per document.

        Args:
            chunks_with_similarity: List of (chunk, similarity) tuples
            top_k: Number of chunks to retrieve per document
            top_n: Total number of documents to retrieve

        Returns:
            List of dictionaries with chunk data
        """
        # Use the base implementation from the search service
        _, _, selected_chunks = self.process_search_results_base(
            chunks_with_similarity, top_k, top_n
        )

        # Convert to the format needed for the tool response
        result_data = []
        for chunk, similarity in selected_chunks:
            result_data.append(
                {
                    "content": chunk.content,
                    "document_name": chunk.document_id.name,
                    "document_id": chunk.document_id.id,
                    "chunk_id": chunk.id,
                    "chunk_name": chunk.name,
                    "similarity": round(similarity, 4),
                    "similarity_percentage": f"{int(similarity * 100)}%",
                }
            )

        return result_data
