import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMDocumentEmbedder(models.Model):
    _inherit = "llm.document"

    def _ensure_index_exists(self, embedding_model_id):
        """
        Ensure a vector index exists for the specified embedding model.

        Args:
            embedding_model_id: The ID of the embedding model
        """
        if not embedding_model_id:
            return False

        # Get the embedding model to determine dimensions
        embedding_model = self.env['llm.model'].browse(embedding_model_id)
        if not embedding_model.exists():
            return False

        # Get sample embedding to determine dimensions
        sample_embedding = embedding_model.embedding("")[0]
        if not sample_embedding:
            return False

        # Get the dimensions from the sample embedding
        dimensions = len(sample_embedding) if isinstance(sample_embedding, list) else sample_embedding.shape[0]

        # Get the pgvector field
        pgvector_field = self.env['llm.document.chunk']._fields['embedding']

        # Generate a unique index name for this model
        table_name = 'llm_document_chunk'
        index_name = f"{table_name}_embedding_model_{embedding_model_id}_idx"

        # Create or ensure the index exists
        pgvector_field.create_index(
            self.env.cr,
            table_name,
            'embedding',
            index_name,
            dimensions=dimensions,
            model_field_name='embedding_model_id',
            model_id=embedding_model_id,
        )

        _logger.info(f"Created/verified index {index_name} for embedding model {embedding_model_id}")
        return True

    def embed(self):
        """Embed the document chunks using vector embeddings"""
        for document in self:
            if document.state != "chunked":
                _logger.warning(
                    "Document %s must be in chunked state to embed", document.id
                )
                continue

            # Ensure embedding model is specified
            if not document.embedding_model_id:
                document._post_message(
                    "Embedding model not specified - please select an embedding model",
                    "error",
                )
                continue

        # Lock documents and process only the successfully locked ones
        documents = self._lock()
        if not documents:
            return False

        for document in documents:
            if not document.embedding_model_id:
                raise UserError(_("Embedding model not specified"))

            embedding_model = document.embedding_model_id

            # Process chunks in batches for efficiency
            chunks_to_process = document.chunk_ids.filtered(lambda c: not c.embedding)
            batch_size = 10  # Adjust based on embedding model capabilities

            chunks_processed = 0
            for i in range(0, len(chunks_to_process), batch_size):
                batch = chunks_to_process[i:i + batch_size]

                # Skip empty batch
                if not batch:
                    continue

                # Get content for all chunks in batch
                # contents = [chunk.content for chunk in batch]

                for chunk in batch:
                    embedding = embedding_model.embedding(chunk.content)[0]
                    chunk.embedding = embedding
                    chunks_processed += 1

            # Update document state if at least one chunk was processed
            if chunks_processed > 0:
                document.write({"state": "ready"})
                document._post_message(
                    f"Embedded {chunks_processed} chunks using {embedding_model.name}",
                    "success",
                )

                # Ensure index exists for this embedding model
                document._ensure_index_exists(embedding_model.id)
            else:
                document._post_message(
                    "No chunks were successfully embedded", "warning"
                )

        # Unlock all successfully processed documents
        documents._unlock()
        return True


    def action_reindex(self):
        """
        Re-index RAG document by recreating vector indices.
        Useful when indices need to be rebuilt.
        """
        self.ensure_one()

        # Check for chunks with embeddings
        chunks_with_embeddings = self.chunk_ids.filtered(lambda c: c.embedding is not None)
        if not chunks_with_embeddings:
            raise UserError(_("No chunks with embeddings found to reindex"))

        # Check for embedding model
        if not self.embedding_model_id:
            raise UserError(_("Embedding model not specified"))

        # Lock document
        self._lock()

        try:
            # Post status message
            self._post_message(
                "Starting re-indexing process...",
                "info"
            )

            # Recreate index
            embedding_model_id = self.embedding_model_id.id
            self._ensure_index_exists(embedding_model_id)

            # Post success message
            self._post_message(
                f"Successfully recreated index for {len(chunks_with_embeddings)} chunks",
                "success"
            )

        except Exception as e:
            # Post error message
            self._post_message(
                f"Error during re-indexing: {str(e)}",
                "error"
            )
            raise UserError(_("Re-indexing failed: %s") % str(e))

        finally:
            # Unlock document
            self._unlock()

    def action_mass_reindex(self):
        """
        Mass reindex multiple RAG documents grouped by embedding model.
        """
        # Filter documents with chunks and embedding model
        documents_with_chunks = self.filtered(
            lambda d: d.chunk_ids and d.chunk_ids.filtered(
                lambda c: c.embedding is not None
            ) and d.embedding_model_id
        )

        if not documents_with_chunks:
            raise UserError(_(
                "No valid documents found for reindexing.\n"
                "Documents must have chunks with embeddings and an embedding model assigned."
            ))

        # Group documents by embedding model for efficient indexing
        docs_by_model = {}
        for doc in documents_with_chunks:
            model_id = doc.embedding_model_id.id
            if model_id not in docs_by_model:
                docs_by_model[model_id] = self.env['llm.document']
            docs_by_model[model_id] |= doc

        # Process each model group
        success_count = 0
        error_count = 0

        for model_id, docs in docs_by_model.items():
            try:
                # Use the first document to represent the group
                docs[0]._ensure_index_exists(model_id)
                success_count += len(docs)
            except Exception as e:
                error_count += len(docs)
                _logger.error(f"Error reindexing documents for model {model_id}: {str(e)}")

        # Show a notification with the results
        message = f"Reindexing complete: {success_count} successful, {error_count} failed."
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Re-index RAG Documents'),
                'message': message,
                'sticky': False,
                'type': 'success' if error_count == 0 else 'warning',
            }
        }
