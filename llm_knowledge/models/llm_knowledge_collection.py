import logging

from odoo import _, api, fields, models
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class LLMKnowledgeCollection(models.Model):
    _name = "llm.knowledge.collection"
    _description = "Knowledge Collection for RAG"
    _inherit = ["llm.store.collection", "mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
    )
    description = fields.Text(
        string="Description",
        tracking=True,
    )
    active = fields.Boolean(
        string="Active",
        default=True,
        tracking=True,
    )
    embedding_model_id = fields.Many2one(
        "llm.model",
        string="Embedding Model",
        domain="[('model_use', '=', 'embedding')]",
        required=True,
        tracking=True,
        help="The model used to create embeddings for documents in this collection",
    )
    resource_ids = fields.Many2many(
        "llm.resource",
        string="Resources",
        relation="llm_knowledge_resource_collection_rel",
        column1="collection_id",
        column2="resource_id",
    )
    # Domain filters for automatically adding resources
    domain_ids = fields.One2many(
        "llm.knowledge.domain",
        "collection_id",
        string="Domain Filters",
        help="Domain filters to select records for RAG document creation",
    )
    resource_count = fields.Integer(
        string="Resource Count",
        compute="_compute_resource_count",
    )
    chunk_count = fields.Integer(
        string="Chunk Count",
        compute="_compute_chunk_count",
    )
    chunk_ids = fields.Many2many(
        "llm.knowledge.chunk",
        string="Chunks (from Resources)",
        compute="_compute_chunk_ids",
        store=False,
        help="Chunks belonging to the resources included in this collection."
    )

    store_id = fields.Many2one(
        "llm.store",
        string="Vector Store",
        required=False,
        ondelete="cascade",
        tracking=True
    )

    @api.depends("resource_ids.chunk_ids")
    def _compute_chunk_ids(self):
        for collection in self:
            collection.chunk_ids = collection.resource_ids.mapped('chunk_ids')

    @api.depends("resource_ids")
    def _compute_resource_count(self):
        for record in self:
            record.resource_count = len(record.resource_ids)

    @api.depends("chunk_ids")
    def _compute_chunk_count(self):
        for record in self:
            record.chunk_count = len(record.chunk_ids)

    def action_view_resources(self):
        """Open a view with all resources in this collection"""
        self.ensure_one()
        return {
            "name": _("Collection Resources"),
            "view_mode": "tree,form",
            "res_model": "llm.resource",
            "domain": [("id", "in", self.resource_ids.ids)],
            "type": "ir.actions.act_window",
            "context": {"default_collection_ids": [(6, 0, [self.id])]},
        }

    def action_view_chunks(self):
        """Open a view with all chunks from resources in this collection"""
        self.ensure_one()

        return {
            "name": _("Collection Chunks"),
            "view_mode": "tree,form",
            "res_model": "llm.knowledge.chunk",
            "domain": [("collection_ids", "=", self.id)],
            "type": "ir.actions.act_window",
        }

    def sync_resources(self):
        """
        Synchronize collection resources with domain filters.
        This will:
        1. Add new resources for records matching domain filters
        2. Remove resources that no longer match domain filters
        """
        for collection in self:
            if not collection.domain_ids:
                continue

            created_count = 0
            linked_count = 0
            removed_count = 0

            # Find all records that match domains across all active domain filters
            matching_records = []
            model_map = {}  # To track which model each record belongs to

            # Process each model and its domain
            for domain_filter in collection.domain_ids.filtered(lambda d: d.active):
                model_name = domain_filter.model_name
                # Validate model exists
                if model_name not in self.env:
                    collection.message_post(
                        body=_(f"Model '{model_name}' not found. Skipping."),
                        message_type="notification",
                    )
                    continue

                # Get model and evaluate domain
                model = self.env[model_name]
                domain = safe_eval(domain_filter.domain)

                # Search records matching the domain
                records = model.search(domain)

                if not records:
                    collection.message_post(
                        body=_(
                            f"No records found for model '{domain_filter.model_id.name}' with given domain."
                        ),
                        message_type="notification",
                    )
                    continue

                # Store model_id with each record for later use
                for record in records:
                    matching_records.append((model_name, record.id))
                    model_map[(model_name, record.id)] = domain_filter.model_id

            # Get all existing resources in the collection
            existing_docs = collection.resource_ids

            # Track which existing resources should be kept
            docs_to_keep = self.env["llm.resource"]

            # Process all matching records to create/link resources
            for model_name, record_id in matching_records:
                # Get actual record
                record = self.env[model_name].browse(record_id)
                model_id = model_map[(model_name, record_id)].id

                # Check if resource already exists for this record
                existing_doc = self.env["llm.resource"].search(
                    [
                        ("model_id", "=", model_id),
                        ("res_id", "=", record_id),
                    ],
                    limit=1,
                )

                if existing_doc:
                    # Document exists - add to keep list if in our collection
                    if existing_doc in existing_docs:
                        docs_to_keep |= existing_doc
                    # Otherwise link it if not already in the collection
                    elif existing_doc.id not in collection.resource_ids.ids:
                        collection.write({"resource_ids": [(4, existing_doc.id)]})
                        linked_count += 1
                        docs_to_keep |= existing_doc
                else:
                    # Create new resource with meaningful name
                    if hasattr(record, "display_name") and record.display_name:
                        name = record.display_name
                    elif hasattr(record, "name") and record.name:
                        name = record.name
                    else:
                        model_display = self.env["ir.model"]._get(model_name).name
                        name = f"{model_display} #{record_id}"

                    new_doc = self.env["llm.resource"].create(
                        {
                            "name": name,
                            "model_id": model_id,
                            "res_id": record_id,
                            "collection_ids": [(4, collection.id)],
                        }
                    )
                    docs_to_keep |= new_doc
                    created_count += 1

            # Find resources to remove (those in the collection but not matching any domains)
            docs_to_remove = existing_docs - docs_to_keep

            # Remove resources that no longer match any domains
            if docs_to_remove:
                # Only remove from this collection, not delete the resources
                collection.write(
                    {"resource_ids": [(3, doc.id) for doc in docs_to_remove]}
                )
                removed_count = len(docs_to_remove)

            # Post summary message
            if created_count > 0 or linked_count > 0 or removed_count > 0:
                collection.message_post(
                    body=_(
                        f"Synchronization complete: Created {created_count} new resources, "
                        f"linked {linked_count} existing resources, "
                        f"removed {removed_count} resources no longer matching domains."
                    ),
                    message_type="notification",
                )
            else:
                collection.message_post(
                    body=_(
                        "No changes made - collection is already in sync with domains."
                    ),
                    message_type="notification",
                )

    def process_resources(self):
        """Process resources through retrieval, parsing, and chunking (up to chunked state)"""
        for collection in self:
            collection.resource_ids.process_resource()

    def reindex_collection(self):
        """
        Reindex all resources in the collection.
        This will clear all chunk embeddings (setting them to NULL),
        reset resource states from 'ready' to 'chunked',
        and rebuild the index to exclude NULL embeddings.
        """
        for collection in self:
            ready_docs = collection.resource_ids.filtered(lambda d: d.state == "ready")
            chunks = self.env["llm.knowledge.chunk"].search(
                [("collection_ids", "=", collection.id)]
            )
            if ready_docs:
                ready_docs.write({"state": "chunked"})

            if chunks:
                # Use embedding_model_id instead of collection_id
                if collection.embedding_model_id:
                    embedding_model_id = collection.embedding_model_id.id

                    # Get sample embedding to determine dimensions
                    sample_embedding = collection.embedding_model_id.embedding("")[0]
                    dimensions = len(sample_embedding) if sample_embedding else None

                    # First clear all embeddings and commit
                    # This is done in one operation to avoid partial states
                    chunks.write(
                        {
                            "embedding": None,
                            "embedding_model_id": embedding_model_id,
                        }
                    )
                    self.env.cr.commit()

                    # Now create the index - it will automatically exclude NULL embeddings
                    # due to the WHERE embedding IS NOT NULL clause in create_embedding_index
                    if dimensions:
                        self.env["llm.knowledge.chunk"].create_embedding_index(
                            embedding_model_id=embedding_model_id,
                            dimensions=dimensions,
                        )

                    collection.message_post(
                        body=_(
                            f"Reset embeddings for {len(chunks)} chunks and recreated index for model {collection.embedding_model_id.name}."
                        ),
                        message_type="notification",
                    )
                else:
                    collection.message_post(
                        body=_(
                            "Cannot reindex: No embedding model configured for this collection."
                        ),
                        message_type="warning",
                    )
            else:
                collection.message_post(
                    body=_("No chunks found to reindex."),
                    message_type="notification",
                )

    def action_open_upload_wizard(self):
        """Open the upload resource wizard with this collection pre-selected"""
        self.ensure_one()
        return {
            "name": "Upload Resources",
            "type": "ir.actions.act_window",
            "res_model": "llm.upload.resource.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_collection_id": self.id,
                "default_resource_name_template": "{filename}",
            },
        }

    def embed_resources(self, specific_resource_ids=None, batch_size=20):
        """
        Embed all chunked resources using the collection's embedding model.
        Optimized to directly filter chunks instead of searching resources first.

        Args:
            specific_resource_ids: Optional list of resource IDs to process.
                                 If provided, only chunks from these resources will be processed.
            batch_size: Number of chunks to process in each batch
        """
        for collection in self:
            if not collection.embedding_model_id:
                collection.message_post(
                    body=_("No embedding model configured for this collection."),
                    message_type="warning",
                )
                continue

            # Directly search for chunks that belong to chunked resources in this collection
            chunk_domain = [
                ("collection_ids", "=", collection.id),
            ]

            # Add specific resource filter if provided
            if specific_resource_ids:
                chunk_domain.append(("resource_id", "in", specific_resource_ids))
            else:
                chunk_domain.append(("resource_id.state", "=", "chunked"))

            # Get all relevant chunks in one query
            chunks = self.env["llm.knowledge.chunk"].search(chunk_domain)

            if not chunks:
                message = _("No chunks found for resources in chunked state")
                if specific_resource_ids:
                    message += _(" for the specified resource IDs")
                collection.message_post(
                    body=message,
                    message_type="notification",
                )
                continue

            # Apply the collection's embedding model
            embedding_model = collection.embedding_model_id

            # Process chunks in batches for efficiency
            total_chunks = len(chunks)
            processed_chunks = 0
            processed_resource_ids = (
                set()
            )  # Track which resource IDs had chunks processed

            # Process in batches
            for i in range(0, total_chunks, batch_size):
                batch = chunks[i: i + batch_size]
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
                    # Track the resource ID for this chunk
                    processed_resource_ids.add(chunk.resource_id.id)

                processed_chunks += len(batch)
                _logger.info(f"Processed {processed_chunks}/{total_chunks} chunks")

                # Commit transaction after each batch to avoid timeout issues
                self.env.cr.commit()

            # Update resource states to ready - only update resources that had chunks processed
            if processed_resource_ids:
                self.env["llm.resource"].browse(list(processed_resource_ids)).write(
                    {"state": "ready"}
                )
                self.env.cr.commit()

                # Prepare message with resource details for clarity
                doc_count = len(processed_resource_ids)
                msg = _(
                    f"Embedded {processed_chunks} chunks from {doc_count} resources using {embedding_model.name}"
                )

                collection.message_post(
                    body=msg,
                    message_type="notification",
                )

                # Create a model-specific index for better performance
                # Use embedding_model_id instead of collection_id
                dimensions = (
                    len(batch_embeddings[0])
                    if batch_embeddings and batch_embeddings[0]
                    else None
                )
                self.env["llm.knowledge.chunk"].create_embedding_index(
                    embedding_model_id=embedding_model.id, dimensions=dimensions
                )

                return {
                    "success": True,
                    "processed_chunks": processed_chunks,
                    "processed_resources": len(processed_resource_ids),
                }
            else:
                collection.message_post(
                    body=_("No chunks were successfully embedded"),
                    message_type="warning",
                )

                return {
                    "success": False,
                    "processed_chunks": 0,
                    "processed_resources": 0,
                }
