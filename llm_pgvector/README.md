# LLM PgVector Module

A powerful Odoo module that integrates the PostgreSQL pgvector extension to enable vector embedding storage and similarity search capabilities for AI/LLM applications.

## Overview

This module provides the foundation for vector-based operations in Odoo, enabling:

- Storage of vector embeddings directly in the PostgreSQL database
- Efficient vector similarity search operations
- Support for different embedding models and dimensions
- Automatic management of vector indices

## Features

- `PgVector` field type for storing embeddings with configurable dimensions
- `EmbeddingMixin` for easy integration of vector search capabilities in any model
- Automatic pgvector extension installation and verification
- Multiple similarity search methods (cosine, inner product, L2 distance)
- Support for model-specific vector indices
- Integration with Odoo's search API

## Requirements

- PostgreSQL 12+ with pgvector extension installed (or installable by superuser)
- Python dependencies:
  - pgvector>=0.4.0
  - numpy

## Installation

### PostgreSQL pgvector Extension

The module will automatically attempt to install the pgvector extension during installation. However, you might need to install it manually on your PostgreSQL server first:

```bash
# On Debian/Ubuntu
sudo apt install postgresql-14-pgvector  # Replace with your PostgreSQL version

# On RHEL/CentOS/Fedora
sudo dnf install pgvector_14  # Replace with your PostgreSQL version

# From source
git clone --branch v0.4.4 https://github.com/pgvector/pgvector.git
cd pgvector
make
sudo make install
```

### Python Dependencies

Install required Python dependencies:

```bash
pip install pgvector numpy
```

### Module Installation

Install the module through the Odoo Apps interface or by adding it to your addons path.

## Usage

### Basic Vector Field Declaration

```python
from odoo import models, fields
from llm_pgvector import PgVector

class Document(models.Model):
  _name = 'document.model'
  _description = 'Document with Vector Embedding'

  name = fields.Char(string="Name", required=True)
  content = fields.Text(string="Content")
  embedding = PgVector(string="Vector Embedding", dimension=1536)
```

### Using the EmbeddingMixin

The `EmbeddingMixin` provides ready-to-use similarity search capabilities:

```python
from odoo import models, fields
from llm_pgvector import EmbeddingMixin

class DocumentChunk(models.Model):
    _name = 'document.chunk'
    _description = 'Document Chunk'
    _inherit = ['llm.embedding.mixin']

    name = fields.Char(string="Chunk Name", required=True)
    content = fields.Text(string="Chunk Content", required=True)
    document_id = fields.Many2one('document.model', string="Document")
```

### Storing Vector Embeddings

```python
def update_embedding(self):
    """Update embeddings using a model"""
    for record in self:
        # Get the model to use for embeddings
        embedding_model = record.embedding_model_id

        # Generate embedding
        embedding = embedding_model.generate_embedding(record.content)

        # Store the embedding
        record.embedding = embedding
```

### Vector Similarity Search

```python
def find_similar_chunks(self, query_text, limit=5):
  """
  Find chunks similar to the query text.
  """
  # Get specific embedding model to use
  embedding_model = self.env['llm.model'].search([
    ('model_use', '=', 'embedding'),
    ('name', '=', 'openai-text-embedding-3-small')
  ], limit=1)

  if not embedding_model:
    raise ValueError("Required embedding model not found")

  # Generate embedding for query
  query_embedding = embedding_model.generate_embedding(query_text)

  # Search for similar chunks using the embedding
  results = self.env['document.chunk'].search(
    [],  # base domain
    query_vector=query_embedding,
    query_min_similarity=0.7,  # Minimum similarity threshold
    query_operator="<=>",  # Cosine distance operator
    limit=limit
  )

  # Results are automatically ordered by similarity
  # You can access similarity scores through the similarity field
  for result in results:
    print(f"Result: {result.name}, Similarity: {result.similarity}")

  return results
```

### Creating Indices for Better Performance

Models inheriting from `EmbeddingMixin` can organize their embeddings into collections and create collection-specific indices for better performance:

```python
class DocumentChunk(models.Model):
  _name = 'document.chunk'
  _description = 'Document Chunk'
  _inherit = ['llm.embedding.mixin']

  name = fields.Char(string="Chunk Name", required=True)
  content = fields.Text(string="Chunk Content", required=True)
  collection_id = fields.Many2one('document.collection', string="Collection")
  embedding_model_id = fields.Many2one('llm.model', string="Embedding Model")

  def ensure_collection_index(self, collection_id=None):
    """
    Ensure a vector index exists for the specified collection.
    """
    # Get the embedding model to determine dimensions
    embedding_model = self.env['llm.model'].search([
      ('model_use', '=', 'embedding'),
      ('id', '=', self.embedding_model_id.id)
    ], limit=1)

    if not embedding_model:
      return

    # Get sample embedding to determine dimensions
    sample_embedding = embedding_model.generate_embedding("")

    # Get the dimensions from the sample embedding
    dimensions = len(sample_embedding)

    # Create collection-specific index
    self.create_embedding_index(
      collection_id=collection_id,
      dimensions=dimensions,
      force=False  # Only create if doesn't exist
    )
```

When searching within a specific collection, the collection-specific index will be used automatically:

```python
def search_in_collection(self, query_text, collection_id, limit=10):
  # Generate query embedding
  embedding_model = self.env['llm.model'].search([
    ('model_use', '=', 'embedding'),
  ], limit=1)

  query_embedding = embedding_model.generate_embedding(query_text)

  # Search using collection filter and vector similarity
  domain = [('collection_id', '=', collection_id)]
  results = self.search(
    domain,
    query_vector=query_embedding,
    limit=limit
  )

  return results
```

## Available Similarity Operators

The vector search supports different similarity metrics via the `query_operator` parameter:

- `<=>`: Cosine distance (range 0-2, lower is more similar)
- `<->`: Euclidean (L2) distance (unbounded, lower is more similar)
- `<#>`: Negative inner product (higher is more similar)

## Performance Considerations

- Create appropriate indices for your vector fields with `create_embedding_index`
- Use domain filtering to limit the search space
- For large datasets, consider using approximate nearest neighbor algorithms (HNSW or IVFFlat)
- Monitor memory usage with high-dimensional vectors

## References

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [PostgreSQL Vector Search](https://www.postgresql.org/docs/current/vectors.html)

## License

LGPL-3.0