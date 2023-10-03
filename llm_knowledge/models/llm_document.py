import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class LLMDocument(models.Model):
    _name = "llm.document"
    _description = "LLM Document for RAG"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
    )
    res_model = fields.Char(
        string="Related Model",
        required=True,
        tracking=True,
        help="The model of the referenced document",
    )
    res_id = fields.Integer(
        string="Related ID",
        required=True,
        tracking=True,
        help="The ID of the referenced document",
    )
    content = fields.Text(
        string="Content",
        help="Markdown representation of the document content",
    )
    external_url = fields.Char(
        string="External URL",
        compute="_compute_external_url",
        store=True,
        help="External URL from the related record if available",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("retrieved", "Retrieved"),
            ("parsed", "Parsed"),
            ("chunked", "Chunked"),
            ("ready", "Ready"),
        ],
        string="State",
        default="draft",
        tracking=True,
    )
    lock_date = fields.Datetime(
        string="Lock Date",
        tracking=True,
        help="Date when the document was locked for processing",
    )
    kanban_state = fields.Selection(
        [
            ("normal", "Ready"),
            ("blocked", "Blocked"),
            ("done", "Done"),
        ],
        string="Kanban State",
        compute="_compute_kanban_state",
        store=True,
    )
    chunk_ids = fields.One2many(
        "llm.document.chunk",
        "document_id",
        string="Chunks",
    )
    chunk_count = fields.Integer(
        string="Chunk Count",
        compute="_compute_chunk_count",
        store=True,
    )
    collection_ids = fields.Many2many(
        "llm.document.collection",
        relation="llm_document_collection_rel",
        column1="document_id",
        column2="collection_id",
        string="Collections",
    )

    @api.depends("res_model", "res_id")
    def _compute_external_url(self):
        """Compute external URL from related record if available"""
        for document in self:
            document.external_url = False
            if not document.res_model or not document.res_id:
                continue

            try:
                # Get the related record
                if document.res_model in self.env:
                    record = self.env[document.res_model].browse(document.res_id)
                    if not record.exists():
                        continue

                    # Case 1: Handle ir.attachment with type 'url'
                    if document.res_model == "ir.attachment" and hasattr(
                        record, "type"
                    ):
                        if record.type == "url" and hasattr(record, "url"):
                            document.external_url = record.url

                    # Case 2: Check if record has an external_url field
                    elif hasattr(record, "external_url"):
                        document.external_url = record.external_url

            except Exception as e:
                _logger.warning(
                    "Error computing external URL for document %s: %s",
                    document.id,
                    str(e),
                )
                continue

    @api.depends("chunk_ids")
    def _compute_chunk_count(self):
        for record in self:
            record.chunk_count = len(record.chunk_ids)

    @api.depends("lock_date")
    def _compute_kanban_state(self):
        for record in self:
            record.kanban_state = "blocked" if record.lock_date else "normal"

    def action_view_chunks(self):
        """Open a view with all chunks for this document"""
        self.ensure_one()
        return {
            "name": _("Document Chunks"),
            "view_mode": "tree,form",
            "res_model": "llm.document.chunk",
            "domain": [("document_id", "=", self.id)],
            "type": "ir.actions.act_window",
            "context": {"default_document_id": self.id},
        }

    def _post_message(self, message, message_type="info"):
        """
        Post a message to the document's chatter with appropriate styling.

        Args:
            message (str): The message to post
            message_type (str): Type of message (error, warning, success, info)
        """
        if message_type == "error":
            body = f"<p class='text-danger'><strong>Error:</strong> {message}</p>"
        elif message_type == "warning":
            body = f"<p class='text-warning'><strong>Warning:</strong> {message}</p>"
        elif message_type == "success":
            body = f"<p class='text-success'><strong>Success:</strong> {message}</p>"
        else:  # info
            body = f"<p><strong>Info:</strong> {message}</p>"

        return self.message_post(
            body=body,
            message_type="comment",
        )

    def _lock(self):
        """Lock documents for processing and return the ones successfully locked"""
        successfully_locked = self.env["llm.document"]
        for document in self:
            if document.lock_date:
                _logger.warning(
                    "Document %s is already locked for processing", document.id
                )
                continue
            document.lock_date = fields.Datetime.now()
            successfully_locked |= document
        return successfully_locked

    def _unlock(self):
        """Unlock documents after processing"""
        return self.write({"lock_date": False})

    def process_document(self):
        """
        Process documents through the entire pipeline.
        Can handle multiple documents at once, processing them through
        as many pipeline stages as possible based on their current states.
        """
        # Process each stage with the filtered recordsets
        # Each method will only process documents in the appropriate state

        # Stage 1: Retrieve content for draft documents
        draft_docs = self.filtered(lambda d: d.state == "draft")
        if draft_docs:
            draft_docs.retrieve()

        # Stage 2: Parse retrieved documents
        retrieved_docs = self.filtered(lambda d: d.state == "retrieved")
        if retrieved_docs:
            retrieved_docs.parse()

        # Stage 3: Chunk parsed documents
        parsed_docs = self.filtered(lambda d: d.state == "parsed")
        if parsed_docs:
            parsed_docs.chunk()

        # Stage 4: Embed chunked documents
        chunked_docs = self.filtered(lambda d: d.state == "chunked")
        if chunked_docs:
            chunked_docs.embed()

        return True

    def action_embed(self):
        """Action handler for embedding document chunks"""
        result = self.embed()

        # Return appropriate notification
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Embedding"),
                "message": _("Document embedding process completed."),
                "type": "success" if result else "warning",
                "sticky": False,
            },
        }

    def action_reindex(self):
        """Reindex a single document's chunks"""
        self.ensure_one()

        # Get all chunks for this document
        chunks = self.chunk_ids

        if not chunks:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Reindexing"),
                    "message": _("No chunks found for this document."),
                    "type": "warning",
                },
            }

        # Get all collections this document belongs to
        collections = self.collection_ids

        # Reindex for each collection
        for collection in collections:
            # Get chunks that belong to this collection
            collection_chunks = chunks.filtered(
                lambda c, collection_id=collection.id: collection_id
                in c.collection_ids.ids
            )
            if collection_chunks:
                # Use embedding_model_id instead of collection_id
                embedding_model_id = collection.embedding_model_id.id
                sample_embedding = collection.embedding_model_id.embedding("")[0]
                dimensions = len(sample_embedding) if sample_embedding else None
                collection_chunks.create_embedding_index(
                    embedding_model_id=embedding_model_id,
                    force=True,
                    dimensions=dimensions,
                )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reindexing"),
                "message": _(
                    f"Reindexing request submitted for {len(collections)} collections."
                ),
                "type": "success",
            },
        }

    def action_mass_reindex(self):
        """Reindex multiple documents at once"""
        collections = self.env["llm.document.collection"]
        for document in self:
            # Add to collections set
            collections |= document.collection_ids

        # Reindex each affected collection
        for collection in collections:
            collection.reindex_collection()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reindexing"),
                "message": _(
                    f"Reindexing request submitted for {len(collections)} collections."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    def action_embed(self):
        """
        Embed the document chunks in all collections that this document belongs to.
        This will call the embed_documents method on each collection, but filtering
        to only embed the current document.
        """
        self.ensure_one()

        # Check if document is in chunked state
        if self.state != "chunked":
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Embedding"),
                    "message": _("Document must be in 'chunked' state to be embedded."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Check if document belongs to any collections
        if not self.collection_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Embedding"),
                    "message": _(
                        "Document doesn't belong to any collections. Add it to a collection first."
                    ),
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Process each collection
        embed_count = 0
        for collection in self.collection_ids:
            # We need to modify the embedding logic to only embed chunks from this document
            # Get all chunks for this document
            chunks = self.chunk_ids

            if not chunks:
                continue

            # Apply the collection's embedding model
            embedding_model = collection.embedding_model_id
            if not embedding_model:
                self._post_message(
                    f"Collection {collection.name} has no embedding model configured.",
                    "warning",
                )
                continue

            # Process chunks in batches for efficiency
            batch_size = 20
            total_chunks = len(chunks)
            processed_chunks = 0

            # Process in batches
            for i in range(0, total_chunks, batch_size):
                batch = chunks[i : i + batch_size]
                batch_contents = [chunk.content for chunk in batch]

                # Generate embeddings for all content in the batch at once
                batch_embeddings = embedding_model.embedding(batch_contents)

                # Apply embeddings to each chunk in the batch and add to collection
                for j, chunk in enumerate(batch):
                    # Update with a single write operation per chunk
                    chunk.write(
                        {
                            "embedding": batch_embeddings[j],
                            "embedding_model_id": embedding_model.id,
                            "collection_ids": [(4, collection.id)],
                        }
                    )

                processed_chunks += len(batch)
                _logger.info(
                    f"Processed {processed_chunks}/{total_chunks} chunks for document {self.name}"
                )

                # Commit transaction after each batch to avoid timeout issues
                self.env.cr.commit()

            if processed_chunks > 0:
                embed_count += 1
                # Post message about successful embedding
                self._post_message(
                    f"Successfully embedded {processed_chunks} chunks in collection {collection.name}",
                    "success",
                )

        # Update document state to ready if any embeddings were done
        if embed_count > 0:
            self.write({"state": "ready"})

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Embedding"),
                "message": _("Document embedded successfully in %s collection(s).")
                % embed_count,
                "type": "success",
                "sticky": False,
            },
        }
    def embed(self):
        """
        Embed document chunks in collections by calling the collection's embed_documents method.
        Called after chunking to create vector representations.

        Returns:
            bool: True if any documents were successfully embedded, False otherwise
        """
        # Filter to only get documents in chunked state
        chunked_docs = self.filtered(lambda d: d.state == "chunked")

        if not chunked_docs:
            return False

        # Get all collections for these documents
        collections = self.env['llm.document.collection']
        for doc in chunked_docs:
            collections |= doc.collection_ids

        # If no collections, documents can't be embedded
        if not collections:
            return False

        # Track if any documents were embedded
        any_embedded = False

        # Let each collection handle the embedding
        for collection in collections:
            result = collection.embed_documents(specific_document_ids=chunked_docs.ids)
            # If any collection successfully embedded documents, mark as successful
            if result.get('success') and result.get('processed_documents', 0) > 0:
                any_embedded = True

        # Return True only if documents were actually embedded
        return any_embedded

    @api.model
    def action_mass_process_documents(self):
        """
        Server action handler for mass processing documents.
        This will be triggered from the server action in the UI.
        """
        active_ids = self.env.context.get('active_ids', [])
        if not active_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Documents Selected"),
                    "message": _("Please select documents to process."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        documents = self.browse(active_ids)
        # Process all selected documents
        documents.process_document()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Document Processing"),
                "message": _("%s documents processing started") % len(documents),
                "sticky": False,
                "type": "success",
            },
        }