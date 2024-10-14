# LLM Chroma

A Chroma vector store integration for Odoo that enables storing and querying embeddings via the Chroma HTTP API.

## Features

- **Chroma HTTP Client**: Connect to a Chroma server with optional SSL and API key support.
- **Collection Management**: Create, list, delete, and verify collections in Chroma directly from Odoo.
- **Vector Operations**: Insert, delete, and search vectors with metadata, IDs, and customizable distance‑to‑similarity conversion.
- **Filter Conversion**: Translate basic Odoo filter formats into Chroma `where` conditions.

## Requirements

- Odoo 16.0
- Python dependencies:
  - `chromadb-client`
  - `numpy`

## Installation

1. Place the module in your Odoo `addons` directory.
2. Install Python dependencies in your virtual environment:
   ```bash
   pip install chromadb-client numpy
   ```
3. Update app list and install **LLM Chroma** from Odoo Apps.

## Configuration

1. In **LLM > Configurations > Vector Stores**, create or edit a store:
   - **Service**: `chroma`
   - **Connection URI**: e.g. `http://localhost:8000`
   - **API Key** (optional)
2. Ensure your Chroma Docker image matches the client version. For example:
   ```yaml
   image: chromadb/chroma:1.0.0
   ```

## Usage

Once configured, use the `llm.store` methods:

```python
# Create a new collection
store.chroma_create_collection(collection_id)

# Insert embeddings
store.chroma_insert_vectors(collection_id, vectors, metadata=list_of_dicts, ids=list_of_ids)

# Query by embedding or text
results = store.chroma_search_vectors(collection_id, query_vector, limit=10)
```

## Troubleshooting

### KeyError: '_type'

**Symptom:** A `KeyError: '_type'` when calling `client.create_collection(...)`.

**Cause:** Chroma server expects a `_type` discriminator in the JSON `configuration` payload but didn’t receive one, often due to a client/server version mismatch or omitted default config.

**Solutions:**

1. **Pin matching versions**
   ```bash
   pip install chromadb-client==1.0.0
   docker pull chromadb/chroma:1.0.0
   ```
2. **Explicitly supply configuration**
   ```python
   client.create_collection(
       name=collection_name,
       metadata=metadata,
       configuration={
           "_type": "hnsw",
           "hnsw:space": "cosine",
           # add other settings if needed
       }
   )
   ```

## License

This module is released under the **LGPL-3** license.

