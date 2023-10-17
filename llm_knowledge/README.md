# LLM RAG - Retrieval Augmented Generation for Odoo

This module implements Retrieval Augmented Generation (RAG) for the LLM module in Odoo, providing a complete pipeline for processing documents and making them available for AI-powered search and generation.

## Features

- **Document Management**: Dedicated system for organizing and tracking RAG documents
- **Complete RAG Pipeline**: Process documents through retrieval, parsing, chunking, and embedding
- **Vector Search**: Semantic search capabilities using pgvector for PostgreSQL
- **Multiple Document Sources**: Support for Odoo records, file uploads, and external URLs
- **Extensible Architecture**: Easy to extend with custom parsers, chunkers, and retrievers
- **User-Friendly Wizards**: Intuitive interfaces for creating and managing documents
- **Collection Management**: Group documents into collections for targeted retrieval
- **HTTP Retrieval**: Fetch and process content from external URLs
- **PDF Processing**: Advanced PDF handling with text and image extraction

## Pipeline Overview

Documents flow through a well-defined pipeline:

1. **Retrieval**: Extract document content from source records or external URLs
2. **Parsing**: Convert document content to a standardized format (markdown)
3. **Chunking**: Split documents into semantic chunks for effective retrieval
4. **Embedding**: Create vector representations of chunks for semantic search

## Technical Details

### Extensibility

The module is designed to be highly extensible at every stage of the pipeline:

- **Retrievers**: Custom retrieval logic for different document types
    - Default Retriever: Works with any Odoo record
    - HTTP Retriever: Fetches content from external URLs

- **Parsers**: Support for different file formats
    - Default Parser: Generic parser for Odoo records
    - JSON Parser: Structured output for record data
    - PDF Parser: Extracts text and images from PDF files
    - Text Parser: Handles plain text files

- **Chunkers**: Different algorithms for document segmentation
    - Default Chunker: Splits text into overlapping chunks with configurable size

- **Embedding Models**: Integration with vector embedding models
    - Uses the `llm_pgvector` module for vector storage and search

### Collections

Documents are organized into collections, which:
- Share the same embedding model
- Can be queried as a unified knowledge base
- Support domain-based document addition
- Allow for document uploading directly from files or URLs

### Integration with PostgreSQL

- Uses pgvector extension for efficient vector search
- Creates optimized indices for each embedding model
- Supports cosine similarity for semantic matching

## Installation

### Dependencies

The module has the following dependencies:

- `llm`: Base LLM module
- `llm_pgvector`: PostgreSQL vector extension integration

### Python Dependencies

- `PyMuPDF`: For PDF processing
- `numpy`: For numerical operations
- `requests`: For HTTP retrieval
- `markdownify`: For HTML to markdown conversion

## Usage

### Creating RAG Documents

**From Odoo Records:**
1. Select records in any model
2. Use the "Create RAG Document" action
3. Configure document processing options
4. Process documents through the pipeline

**From Files:**
1. Open a collection
2. Click "Upload Documents"
3. Select local files or provide URLs
4. Configure processing options

**From Domain Queries:**
1. Open a collection
2. Add domains for specific models
3. Click "Add Documents from Domain"
4. Process the created documents

### Processing Documents

Documents can be processed:
- Individually from their form view
- In batches from the document list view
- Automatically during creation by enabling "Process Immediately"
- At the collection level with the "Process Documents" button

### Searching with RAG

The module creates vector embeddings that can be used by the LLM module to perform semantic searches. Document chunks can be directly searched using the Document Chunks view with the vector search option.

## Development

### Adding Custom Retrievers

Extend the `_get_available_retrievers` method in `llm_document_retrievers.py` and implement your custom retrieval logic.

```python
@api.model
def _get_available_retrievers(self):
    retrievers = super()._get_available_retrievers()
    retrievers.append(("my_retriever", "My Custom Retriever"))
    return retrievers
```

### Adding Custom Parsers

Extend the `_get_available_parsers` method in `llm_document_parsers.py` and implement your custom parsing logic.

```python
@api.model
def _get_available_parsers(self):
    parsers = super()._get_available_parsers()
    parsers.append(("my_parser", "My Custom Parser"))
    return parsers

def _parse_my_parser(self, record):
    # Implement custom parsing logic
    return True
```

### Adding Custom Chunkers

Extend the `_get_available_chunkers` method in `llm_document_chunkers.py` and implement your custom chunking algorithm.

```python
@api.model
def _get_available_chunkers(self):
    chunkers = super()._get_available_chunkers()
    chunkers.append(("my_chunker", "My Custom Chunker"))
    return chunkers

def _chunk_my_chunker(self):
    # Implement custom chunking logic
    return True
```

## Model Overview

- **llm.document**: Main document model managing the RAG pipeline
- **llm.document.chunk**: Document segments with vector embeddings
- **llm.document.collection**: Groups of documents sharing an embedding model
- **llm.create.rag.document.wizard**: Wizard for creating documents from records
- **llm.upload.document.wizard**: Wizard for uploading documents from files/URLs
- **llm.add.domain.wizard**: Wizard for adding domain filters to collections

## License

This module is licensed under LGPL-3.

## Credits

Developed by Apexive Solutions LLC
