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
- **Multiple index support** for different embedding models with varying dimensions
- Intelligent management of model-specific vector indices
- Multiple similarity search methods (cosine, inner product, L2 distance)
- Optimized performance for large vector datasets

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

### Vector Similarity Search with Model Filtering

When working with multiple embedding models, it's important to search only within the embedding space of a specific model. Here's how to perform model-specific searches:

```python
def find_similar_chunks(self, query_text, limit=5):
    """
    Find chunks similar to the query text.
    
    This implementation specifically filters by embedding model to ensure
    we're only comparing vectors within the same embedding space.
    """
    # Get specific embedding model to use
    embedding_model = self.env['llm.model'].search([
        ('model_use', '=', 'embedding'),
        ('name', '=', 'openai-text-embedding-3-small')  # Be specific about which model to use
    ], limit=1)
    
    if not embedding_model:
        raise ValueError("Required embedding model not found")
    
    # Generate embedding for query using the same model that created our stored embeddings
    query_embedding = embedding_model.generate_embedding(query_text)
    
    # Search for similar chunks using the embedding
    # CRITICAL: Filter by embedding_model_id to ensure we only compare compatible vectors
    chunks, similarities = self.env['document.chunk'].search_similar(
        query_vector=query_embedding,
        domain=[('embedding_model_id', '=', embedding_model.id)],  # Only search vectors from this model
        limit=limit,
        min_similarity=0.7,  # Minimum similarity threshold
        operator="<=>"  # Cosine distance operator
    )
    
    return chunks, similarities
```

This approach ensures that:

1. You only compare vectors created by the same embedding model
2. Your search leverages the model-specific index created earlier
3. Similarity scores are meaningful since all vectors have the same dimensionality
4. You can run multiple embedding models in parallel without interference

### Available Similarity Operators

The `search_similar` method supports different similarity metrics via the `operator` parameter:

- `<=>`: Cosine distance (default, range 0-2, lower is more similar)
- `<->`: Euclidean (L2) distance (unbounded, lower is more similar)
- `<#>`: Negative inner product (-cosine for normalized vectors, higher is more similar)

### Creating and Managing Model-Specific Indices

A key feature of this module is its ability to maintain separate indices for different embedding models, each with their own dimension requirements:

```python
# Create a model-specific index for optimized searching
def ensure_index_exists(self, embedding_model_id):
    """
    Ensure a vector index exists for the specified embedding model.
    
    This is crucial when working with multiple embedding models that 
    produce vectors of different dimensions (e.g., OpenAI vs. local models).
    Each model gets its own optimized index.
    """
    if not embedding_model_id:
        return False
    
    # Get the embedding model to determine dimensions
    embedding_model = self.env['llm.model'].browse(embedding_model_id)
    if not embedding_model.exists():
        return False
    
    # Get sample embedding to determine dimensions
    sample_embedding = embedding_model.generate_embedding("")
    
    # Get the dimensions from the sample embedding
    dimensions = (
        len(sample_embedding) 
        if isinstance(sample_embedding, list) 
        else sample_embedding.shape[0]
    )
    
    # Get the pgvector field
    pgvector_field = self.env['document.chunk']._fields['embedding']
    
    # Generate a unique index name for this model
    table_name = "document_chunk"
    index_name = f"{table_name}_emb_model_{embedding_model_id}_idx"
    
    # Create or ensure the index exists - this is model-specific!
    pgvector_field.create_index(
        self.env.cr,
        table_name,
        "embedding",
        index_name,
        dimensions=dimensions,
        model_field_name="embedding_model_id",  # Field that stores which model created the embedding
        model_id=embedding_model_id             # The specific model ID to filter by
    )
    
    return True
```

This approach allows you to:

1. Work with multiple embedding models in the same application
2. Create optimized indices for each model's specific dimensionality
3. Efficiently filter searches to only include vectors created by a specific model
4. Upgrade or change embedding models without rebuilding your entire database

## Advanced Usage

### Using Different Vector Dimensions

The module supports embedding models with different vector dimensions. You can use this to switch between models or support multiple models simultaneously:

```python
class DocumentChunk(models.Model):
    _name = 'document.chunk'
    _inherit = ['llm.embedding.mixin']
    
    # Fields to track which model created the embedding
    embedding_model_id = fields.Many2one(
        'llm.model', 
        string="Embedding Model",
        domain="[('model_use', '=', 'embedding')]"
    )
    
    def update_embeddings_for_model(self, model_id):
        """Update embeddings for a specific model"""
        model = self.env['llm.model'].browse(model_id)
        
        # Process chunks in batches
        for chunk in self:
            embedding = model.generate_embedding(chunk.content)
            chunk.write({
                'embedding': embedding,
                'embedding_model_id': model_id
            })
        
        # Ensure index exists for this model
        self._ensure_index_exists(model_id)
        
        return True
    
    def migrate_to_new_model(self, old_model_id, new_model_id):
        """Migrate chunks from one embedding model to another"""
        # Find chunks using the old model
        chunks = self.search([('embedding_model_id', '=', old_model_id)])
        
        # Update embeddings with the new model
        chunks.update_embeddings_for_model(new_model_id)
        
        return True
```

### Custom Similarity Search

For more control over the search process, you can execute raw SQL queries:

```python
def custom_vector_search(self, query_vector, domain, limit=10):
    """Custom vector search implementation"""
    from pgvector import Vector
    
    # Format the query vector
    vector_str = Vector._to_db(query_vector)
    
    # Convert domain to SQL WHERE clause
    query_obj = self.env['document.chunk'].sudo()._where_calc(domain)
    tables, where_clause, where_params = query_obj.get_sql()
    
    # Customize the query as needed
    query = f"""
        WITH query_vector AS (
            SELECT '{vector_str}'::vector AS vec
        )
        SELECT id, 1 - (embedding <=> query_vector.vec) as similarity
        FROM document_chunk, query_vector
        WHERE embedding IS NOT NULL
        AND {where_clause}
        ORDER BY similarity DESC
        LIMIT %s
    """
    
    self.env.cr.execute(query, where_params + [limit])
    results = self.env.cr.fetchall()
    
    record_ids = [row[0] for row in results]
    similarities = [row[1] for row in results]
    
    return self.env['document.chunk'].browse(record_ids), similarities
```

### Hybrid Search (Vector + Keyword)

```python
def hybrid_search(self, query_text, keywords, limit=10):
    """Combined vector and keyword search"""
    embedding_model = self.embedding_model_id
    query_vector = embedding_model.generate_embedding(query_text)
    
    # First find candidates with keyword search
    keyword_domain = [('content', 'ilike', keywords)]
    candidates = self.search(keyword_domain, limit=limit*2)
    candidate_ids = candidates.ids
    
    # Then refine with vector search
    if candidate_ids:
        domain = [('id', 'in', candidate_ids)]
        results, similarities = self.search_similar(
            query_vector, 
            domain=domain,
            limit=limit
        )
        return results, similarities
    
    # Fallback to pure vector search if no keyword matches
    return self.search_similar(query_vector, limit=limit)
```

## Performance Considerations

- Create appropriate indices for your vector fields
- Use domain filtering to limit the search space
- For large datasets, consider using approximate nearest neighbor algorithms (HNSW or IVFFlat)
- Monitor memory usage with high-dimensional vectors

## References

- [pgvector Documentation](https://github.com/pgvector/pgvector)
- [PostgreSQL Vector Search](https://www.postgresql.org/docs/current/vectors.html)

## License

LGPL-3.0

---

This module is part of the Odoo LLM modules suite and is compatible with the `llm` and `llm_rag` modules.
