# LLM Vector Store Base for Odoo

This module extends the base LLM integration module to provide support for vector databases in Odoo applications. It offers a framework for connecting to various vector store providers and abstracting away the implementation details, making it easy to build RAG (Retrieval Augmented Generation) applications.

## Features

- **Vector Store Connectivity**: Connect to various vector databases
- **Provider-Agnostic Interface**: Common API across different vector store providers
- **Collection Management**: Abstract model for working with vector collections
- **Vector Operations**: Insert, search, and delete vectors with metadata

## Vector Store Framework

The vector store framework allows you to:

1. **Connect to Various Vector Databases**: Support for vector stores like Qdrant, Chroma, PostgreSQL, and others through extension modules
2. **Manage Collections**: Create, delete, and list collections within your vector store
3. **Vector Operations**: Insert, search, and delete vectors with metadata
4. **Index Management**: Create and manage indices for optimal search performance

### Architecture

The vector store integration follows a provider pattern:

- **Base Models**: `llm.store` provides the foundation
- **Abstract Collection Model**: `llm.store.collection` serves as a base for concrete implementations
- **Provider Pattern**: Extensible architecture using dispatch methods to support different vector store implementations
- **No Implementation Lock-in**: Easily switch between vector store providers with a consistent API

### Usage Example

```python
# Get a configured vector store
store = env.ref('your_module.your_vector_store')

# Create a collection
store.create_collection('my_collection', dimension=1536)

# Insert vectors
vectors = [[0.1, 0.2, ...], [0.3, 0.4, ...]]  # Your embedding vectors
metadata = [{'text': 'Document 1'}, {'text': 'Document 2'}]
store.insert_vectors('my_collection', vectors, metadata=metadata)

# Search vectors
query_vector = [0.2, 0.3, ...]  # Your query embedding
results = store.search_vectors('my_collection', query_vector, limit=5)
```

## Installation

1. Ensure the base LLM module is installed
2. Install this module in your Odoo instance
3. Configure vector stores through the LLM > Configuration > Vector Stores menu

## Extending with Providers

To add support for a specific vector database:

1. Create a new module that depends on `llm_store`
2. Extend the `llm.store` model and implement the service-specific methods
3. Register your service in the selection field through `_get_available_services()`

Example:

```python
class MyVectorStore(models.Model):
    _inherit = "llm.store"
    
    @api.model
    def _get_available_services(self):
        return super()._get_available_services() + [('my_provider', 'My Vector Store')]
    
    def my_provider_create_collection(self, name, dimension=None, metadata=None, **kwargs):
        # Implementation for creating a collection in your vector store
        pass
        
    # Implement other methods...
```

## Security

The module uses the same security model as the base LLM module, with the LLM Manager group having full access to vector stores.

## License

LGPL-3
