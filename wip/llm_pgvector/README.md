# LLM PgVector Module

A lightweight Odoo module that adds PostgreSQL vector field and similarity search capabilities using pgvector extension.

## Features

- `PgVector` field type supporting variable-dimension vectors
- `EmbeddingMixin` for vector similarity search operations
- Automatic pgvector extension installation
- Index creation and management utilities
- Efficient vector similarity search using native PostgreSQL operations

## Requirements

- PostgreSQL with pgvector extension installed (or installable)
- Python dependencies: pgvector, numpy

## Installation

The module will attempt to install the pgvector extension automatically during installation.
However, you might need to install it manually on your PostgreSQL server first:

```bash
# On Debian/Ubuntu
sudo apt install postgresql-14-pgvector  # Replace 14 with your PostgreSQL version

# From source
git clone --branch v0.4.4 https://github.com/pgvector/pgvector.git
cd pgvector
make
make install
```

Install Python dependencies:

```bash
pip install pgvector numpy
```

## Usage

### Basic Field Declaration

```python
from odoo import models, fields
from llm_pgvector import PgVector

class MyModel(models.Model):
    _name = 'my.model'

    name = fields.Char()
    description = fields.Text()
    embedding = PgVector(string="Vector Embedding")
```

### Using the EmbeddingMixin

```python
from odoo import models, fields
from llm_pgvector import EmbeddingMixin, PgVector

class VectorSearchableModel(models.Model):
    _name = 'my.searchable.model'
    _inherit = ['llm.embedding.mixin']

    name = fields.Char()
    content = fields.Text()
    embedding = PgVector()

    def find_matches(self, query_vector, limit=5):
        records, similarities = self.search_similar(
            query_vector=query_vector,
            limit=limit,
            min_similarity=0.7
        )
        return [(r.id, r.name, sim) for r, sim in zip(records, similarities)]
```

### Creating Indices

```python
# Create a general index
pgvector_field = self._fields['embedding']
pgvector_field.create_index(
    self.env.cr,
    self._table,
    'embedding',
    'my_model_embedding_idx'
)

# Create a model-specific index (for when you have embeddings from different models)
pgvector_field.create_index(
    self.env.cr,
    self._table,
    'embedding',
    f"{self._table}_emb_model_{model_id}_idx",
    dimensions=1536,
    model_field_name='embedding_model_id',
    model_id=model_id
)
```

### Vector Similarity Search

```python
# Simple search
matching_records, similarity_scores = record.search_similar(query_vector)

# With domain filtering
domain = [('is_published', '=', True)]
matching_records, similarity_scores = record.search_similar(
    query_vector,
    domain=domain,
    limit=10,
    min_similarity=0.8
)

# Getting results with scores
results = []
for record, score in zip(matching_records, similarity_scores):
    results.append({
        'id': record.id,
        'name': record.name,
        'similarity': score
    })
```

### Integration with Embedding Models

This module provides only the vector field and search functionality. To use it effectively, combine it with an embedding model implementation:

```python
# Example with an external embedding model
def create_embeddings(self):
    for record in self:
        if not record.content:
            continue

        # Get embedding from your model
        embedding = your_embedding_model.embed_text(record.content)

        # Store in the PgVector field
        record.embedding = embedding
```

## Notes

- The `embedding` field is assumed to be named this way in search functions. If you use a different name, adjust the search implementation.
- Vector dimensions are flexible and determined by the data you store.
- This module only handles the vector field and search capabilities. The embedding model implementation should be provided separately.
