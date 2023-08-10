### Creating Indices for Better Performance

Models inheriting from `EmbeddingMixin` can organize their embeddings into collections and create collection-specific indices for better performance:

```python
class DocumentChunk(models.Model):
  _name = 'document.chunk'
  _description = 'Document Chunk'
  _inherit = ['llm.embedding.mixin']

  name = fields.Char(string="Chunk Name", required=True)
  content = fields.Text(string="Chunk Content", required=True)
  collection_ids = fields.Many2many('document.collection', string="Collections")
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
  domain = [('collection_ids', '=', collection_id)]
  results = self.search(
    domain,
    query_vector=query_embedding,
    limit=limit
  )

  return results
```
