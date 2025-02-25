# LLM Knowledge

This Odoo module implements Retrieval Augmented Generation (RAG) capabilities for the LLM framework, providing document chunking and vector embedding for enhanced AI responses.

## Features

- **Document Collections**: Organize resources into collections for targeted knowledge retrieval
- **Document Chunking**: Split documents into manageable chunks for more precise retrieval
- **Vector Embeddings**: Generate embeddings for semantic search capabilities
- **Vector Store Integration**: Seamless integration with multiple vector database options:
  - PgVector: Native PostgreSQL vector storage and search
  - Chroma: Integration with Chroma vector database
  - Qdrant: Support for Qdrant vector search engine
- **PDF Processing**: Extract and process text from PDF documents

## Installation

1. Clone the repository into your Odoo addons directory.
2. Install the module via the Odoo Apps menu.
3. Install at least one vector store integration (llm_pgvector, llm_chroma, or llm_qdrant).

## Configuration

1. Navigate to LLM > Knowledge > Collections
2. Create a new collection and configure the embedding model
3. Add resources to the collection either manually or using domain filters
4. Process resources to generate chunks and embeddings

## Usage

### Creating a Knowledge Collection

1. Go to LLM > Knowledge > Collections
2. Click "Create" to add a new collection
3. Configure the collection with a name and embedding model
4. Add resources to the collection

### Processing Resources

1. Select resources in the collection
2. Use the "Process Resources" action to:
   - Retrieve content from sources
   - Parse content into markdown
   - Split content into chunks
   - Generate embeddings for each chunk

### Using in RAG

The processed collections can be used in LLM conversations for retrieval augmented generation:

1. Enable RAG in a thread
2. Select the relevant collections
3. The LLM will automatically retrieve relevant chunks based on the conversation context

## Dependencies

- Odoo 16.0 or later
- Python 3.8 or later
- Required Odoo modules:
  - llm
  - llm_resource
  - llm_store
- Python libraries:
  - PyMuPDF
  - numpy
- At least one vector store integration:
  - llm_pgvector (requires pgvector extension for PostgreSQL)
  - llm_chroma (requires chromadb-client)
  - llm_qdrant (requires qdrant-client)

## Contributing

Contributions are welcome! Please follow the contribution guidelines in the repository.

## License

This module is licensed under the LGPL-3 license.
