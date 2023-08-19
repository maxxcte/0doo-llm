# LLM RAG - Retrieval Augmented Generation for Odoo

This module implements Retrieval Augmented Generation (RAG) for the LLM module in Odoo, providing a complete pipeline for processing documents and making them available for AI-powered search and generation.

## Features

- **Document Management**: Dedicated system for organizing and tracking RAG documents
- **Complete RAG Pipeline**: Process documents through retrieval, parsing, chunking, and embedding
- **Vector Search**: Semantic search capabilities using pgvector for PostgreSQL
- **Extensible Architecture**: Easy to extend with custom parsers, chunkers, and retrievers
- **Wizard Interfaces**: User-friendly wizards for creating documents and searching

## Pipeline Overview

Documents flow through a well-defined pipeline:

1. **Retrieval**: Extract document content from source records
2. **Parsing**: Convert document content to a standardized format (markdown)
3. **Chunking**: Split documents into semantic chunks for effective retrieval
4. **Embedding**: Create vector representations of chunks for semantic search

## Technical Details

### Extensibility

The module is designed to be highly extensible:

- **Retrievers**: Custom retrieval logic for different document types
- **Parsers**: Support for different file formats (PDF, text, etc.)
- **Chunkers**: Different algorithms for document segmentation
- **Embedding Models**: Compatibility with various embedding models

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

## Usage

### Creating RAG Documents

1. Select records in any model
2. Use the "Create RAG Document" action
3. Configure document processing options
4. Process documents through the pipeline

### Searching with RAG

1. Open the RAG Search wizard
2. Enter a natural language query
3. Configure search parameters
4. View and use the semantically relevant results

## Development

### Adding Custom Parsers

Extend the `_get_available_parsers` method in `llm_document_parsers.py` and implement your custom parsing logic.

```python
@api.model
def _get_available_parsers(self):
    parsers = super()._get_available_parsers()
    parsers.append(("my_parser", "My Custom Parser"))
    return parsers

def _parse_my_parser(self):
    # Implement custom parsing logic
    return True
```

### Adding Custom Chunkers

Extend the `_get_available_chunkers` method in `llm_document_chunkers.py` and implement your custom chunking algorithm.

### Adding Custom Retrievers

Extend the `_get_available_retrievers` method in `llm_document_retrievers.py` and implement your custom retrieval logic.

## License

This module is licensed under LGPL-3.

## Credits

Developed by Apexive Solutions LLC
