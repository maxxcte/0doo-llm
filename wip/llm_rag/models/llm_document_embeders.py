import logging
from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMDocumentEmbeder(models.Model):
    _inherit = "llm.document"

    @api.onchange('embedding_model_id')
    def _onchange_embedding_model_id(self):
        """When embedding model changes, ensure index exists for that model."""
        if self.embedding_model_id:
            self._ensure_index_exists(self.embedding_model_id.id)

    def _ensure_index_exists(self, embedding_model_id):
        """
        Ensure a vector index exists for the specified embedding model.
        Uses the PgVector field's create_index method.

        Args:
            embedding_model_id: The ID of the embedding model
        """
        if not embedding_model_id:
            return False

        # Get the embedding model to determine dimensions
        embedding_model = self.env['llm.model'].browse(embedding_model_id)
        if not embedding_model.exists():
            return False

        # Get the model dimensions by embedding an empty string and measuring the result

        empty_embedding = embedding_model.embedding("")

        # Determine dimensions from the empty embedding
        if isinstance(empty_embedding, list):
            dimensions = len(empty_embedding)
        elif hasattr(empty_embedding, 'shape'):  # For numpy arrays
            dimensions = empty_embedding.shape[0]

        # Get the pgvector field from document chunk model
        pgvector_field = self.env['llm.document.chunk']._fields['embedding']

        # Create index name
        index_name = f"llm_document_chunk_embedding_model_{embedding_model_id}_idx"

        # Create index if it doesn't exist (force=False)
        pgvector_field.create_index(
            cr=self.env.cr,
            table='llm_document_chunk',
            column='embedding',
            index_name=index_name,
            dimensions=dimensions,  # Pass the dimensions here
            model_field_name="embedding_model_id",
            model_id=embedding_model_id,
            force=False  # Don't recreate if it already exists
        )

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

        try:
            # Process each document
            for document in documents:
                try:
                    # Check if embedding model exists and is configured
                    if not document.embedding_model_id:
                        raise UserError(_("Embedding model not specified"))

                    embedding_model = document.embedding_model_id

                    # Process each chunk
                    chunks_processed = 0
                    for chunk in document.chunk_ids:
                        # Skip chunks that already have embeddings
                        if chunk.embedding:
                            chunks_processed += 1
                            continue

                        # Get embedding from the model
                        try:
                            # Call embedding model to get vector
                            embedding_result = embedding_model.embedding(chunk.content)

                            # Store embedding as vector
                            if embedding_result:
                                chunk.embedding = embedding_result
                                chunks_processed += 1
                        except Exception as e:
                            document._post_message(
                                f"Error embedding chunk {chunk.id}: {str(e)}", "warning"
                            )

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

                except Exception as e:
                    document._post_message(
                        f"Error embedding document: {str(e)}", "error"
                    )
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
            raise UserError(_("Error in batch embedding: %s") % str(e)) from e

    def action_reindex(self):
        """
        Re-index RAG documents by recreating the indices in the database.
        This is useful when the vector indices need to be rebuilt.
        """
        self.ensure_one()

        # Check if there are any chunks to reindex
        if not self.chunk_ids:
            raise UserError(_("No chunks found to reindex"))

        # Get the embedding model
        if not self.embedding_model_id:
            raise UserError(_("Embedding model not specified"))

        # Lock document for processing
        self._lock()

        try:
            # Post a message to the chatter
            self._post_message(
                "Starting re-indexing process...",
                "info"
            )

            # Get all chunk records with embeddings
            chunks_with_embeddings = self.chunk_ids.filtered(lambda c: c.embedding)

            if not chunks_with_embeddings:
                raise UserError(_("No chunks with embeddings found"))

            # Get the embedding model ID
            embedding_model_id = self.embedding_model_id.id

            # Get the pgvector field
            pgvector_field = self.env['llm.document.chunk']._fields['embedding']

            # Create or recreate the index
            index_name = f"llm_document_chunk_embedding_model_{embedding_model_id}_idx"

            # Create the index, forcing recreation
            pgvector_field.create_index(
                cr=self.env.cr,
                table='llm_document_chunk',
                column='embedding',
                index_name=index_name,
                model_field_name="embedding_model_id",
                model_id=embedding_model_id,
                force=True  # Force recreation of the index
            )

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
            # Unlock the document
            self._unlock()

    def action_mass_reindex(self):
        """
        Mass action to reindex multiple RAG documents.
        """
        # Get all documents with chunks
        documents_with_chunks = self.filtered(lambda d: d.chunk_ids and d.embedding_model_id)

        if not documents_with_chunks:
            raise UserError(_("No valid documents found for reindexing.\nDocuments must have chunks and an embedding model assigned."))

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
                # Get the first document to represent the group
                first_doc = docs[0]
                # Use its reindex method which now uses the improved create_index
                first_doc.action_reindex()
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