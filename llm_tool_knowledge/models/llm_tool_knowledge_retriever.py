import logging

from pydantic import BaseModel, ConfigDict, Field

from odoo import api, models

_logger = logging.getLogger(__name__)


class LLMToolKnowledgeRetriever(models.Model):
    _name = "llm.tool"
    _inherit = ["llm.tool"]

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
        Collection = self.env["llm.document.collection"].sudo()
        collections = Collection.search([("active", "=", True)])
        return [(str(collection.id), collection.name) for collection in collections]

    def knowledge_retriever_get_pydantic_model(self):
        """Define the Pydantic model for knowledge retriever parameters"""

        # Get available collections for the dropdown field
        available_collections = self._get_available_collections()
        collections_description = ", ".join(
            [
                f"'{name}' (ID: {collection_id})"
                for collection_id, name in available_collections
            ]
        )

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

        return KnowledgeRetrieverParams

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
        """Process search results to get the top chunks per document.

        Args:
            chunks: Recordset of document chunks with similarity scores in context
            top_k: Number of chunks to retrieve per document
            top_n: Total number of documents to retrieve

        Returns:
            List of dictionaries with chunk data
        """
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
        result_data = []
        for doc_id in top_docs:
            for chunk in chunks_by_doc[doc_id]:
                result_data.append(
                    {
                        "content": chunk.content,
                        "document_name": chunk.document_id.name,
                        "document_id": chunk.document_id.id,
                        "chunk_id": chunk.id,
                        "chunk_name": chunk.name,
                        "similarity": round(chunk.similarity, 4),
                        "similarity_percentage": f"{int(chunk.similarity * 100)}%",
                    }
                )

        return result_data

    def knowledge_retriever_execute(self, parameters):
        """Execute the knowledge retriever tool"""
        _logger.info(f"Executing Knowledge Retriever with parameters: {parameters}")

        # Extract parameters
        query = parameters.get("query")
        collection_id = parameters.get("collection_id")
        top_k = parameters.get("top_k", 5)
        top_n = parameters.get("top_n", 3)
        similarity_cutoff = parameters.get("similarity_cutoff", 0.5)

        if not query:
            return {"error": "Query is required"}

        try:
            # Validate collection exists
            collection = None
            if collection_id:
                collection = self.env["llm.document.collection"].browse(
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
                collection = self.env["llm.document.collection"].search(
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

            # Prepare domain for document chunks
            domain = [
                ("collection_ids", "=", collection.id),
            ]

            # Calculate search limit - get more results for better filtering
            search_limit = top_n * top_k * 2

            # Use the direct search method with vector search parameters
            chunk_model = self.env["llm.document.chunk"]
            chunks = chunk_model.search(
                args=domain,
                limit=search_limit,
                query_vector=query_embedding,
                query_min_similarity=similarity_cutoff,
                query_operator="<=>",  # Cosine similarity
            )

            # Process results to get top chunks per document
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
