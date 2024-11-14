import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
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
        help="Chunks belonging to the resources included in this collection.",
    )

    store_id = fields.Many2one(
        "llm.store",
        string="Vector Store",
        required=True,
        ondelete="cascade",
        tracking=True,
    )

    @api.depends("resource_ids.chunk_ids")
    def _compute_chunk_ids(self):
        for collection in self:
            collection.chunk_ids = collection.resource_ids.mapped("chunk_ids")

    @api.depends("resource_ids")
    def _compute_resource_count(self):
        for record in self:
            record.resource_count = len(record.resource_ids)

    @api.depends("chunk_ids")
    def _compute_chunk_count(self):
        for record in self:
            record.chunk_count = len(record.chunk_ids)

    @api.model_create_multi
    def create(self, vals_list):
        """Extend create to initialize store collection if needed"""
        collections = super().create(vals_list)
        for collection in collections:
            # Initialize the store if one is assigned
            if collection.store_id:
                collection._initialize_store()
        return collections

    def write(self, vals):
        """Extend write to handle embedding model or store changes"""
        # Check for changes to embedding_model_id or store_id
        embedding_model_changed = "embedding_model_id" in vals
        store_changed = "store_id" in vals

        # Store old values for reference
        old_embedding_models = {}
        old_stores = {}
        if embedding_model_changed or store_changed:
            for collection in self:
                old_embedding_models[collection.id] = collection.embedding_model_id.id
                old_stores[collection.id] = (
                    collection.store_id.id if collection.store_id else False
                )

        # Perform the write operation
        result = super().write(vals)

        # Handle changes to embedding model or store
        if embedding_model_changed or store_changed:
            for collection in self:
                # If store changed, initialize the new store
                if store_changed:
                    # First, clean up the old store if it existed
                    if old_stores.get(collection.id):
                        old_store = self.env["llm.store"].browse(
                            old_stores[collection.id]
                        )
                        if old_store.exists():
                            collection._cleanup_old_store(old_store)

                    # Then initialize the new store if it exists
                    if collection.store_id:
                        collection._initialize_store()

                # If embedding model changed but store didn't, resources need to be re-embedded
                # The store doesn't know about embedding models, it just stores vectors
                if embedding_model_changed:
                    # Mark resources for re-embedding
                    ready_resources = collection.resource_ids.filtered(
                        lambda r: r.state == "ready"
                    )
                    if ready_resources:
                        ready_resources.write({"state": "chunked"})

                        collection.message_post(
                            body=_(
                                f"Embedding model changed. Reset {len(ready_resources)} resources for re-embedding."
                            ),
                            message_type="notification",
                        )

        return result

    def unlink(self):
        """Extend unlink to clean up store data"""
        for collection in self:
            # Clean up store data if a store is assigned
            if collection.store_id:
                try:
                    collection.store_id.delete_collection(collection.id)
                except Exception as e:
                    _logger.warning(f"Error deleting collection from store: {str(e)}")
        return super().unlink()

    def _initialize_store(self):
        """Initialize the store for this collection"""
        if not self.store_id:
            return False

        # Create collection in store if it doesn't exist
        collection_exists = self.store_id.collection_exists(self.id)
        _logger.info(f"collection exists {collection_exists}")
        if not collection_exists:
            created = self.store_id.create_collection(self.id)
            if not created:
                raise UserError(
                    _("Failed to create collection in store for collection %s")
                    % self.name
                )

        _logger.info(f"Initialized store for collection {self.name}")

    def _cleanup_old_store(self, old_store):
        """Clean up the old store when switching to a new one"""
        try:
            # Delete the collection from the old store
            if old_store.collection_exists(self.id):
                old_store.delete_collection(self.id)
            return True
        except Exception as e:
            _logger.warning(f"Error cleaning up old store: {str(e)}")
            return False

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
        This will reset resource states from 'ready' to 'chunked',
        and recreate the collection in the store if necessary.
        """
        for collection in self:
            # If we have a store, recreate the collection
            if collection.store_id:
                try:
                    # Delete and recreate the collection in the store
                    if collection.store_id.collection_exists(collection.id):
                        collection.store_id.delete_collection(collection.id)

                    # Create the collection again
                    collection.store_id.create_collection(collection.id)

                    # Mark resources for re-embedding
                    ready_docs = collection.resource_ids.filtered(
                        lambda d: d.state == "ready"
                    )
                    if ready_docs:
                        ready_docs.write({"state": "chunked"})

                        collection.message_post(
                            body=_(
                                f"Reset {len(ready_docs)} resources for re-embedding with model {collection.embedding_model_id.name}."
                            ),
                            message_type="notification",
                        )
                    else:
                        collection.message_post(
                            body=_("No resources found to reindex."),
                            message_type="notification",
                        )
                except Exception as e:
                    collection.message_post(
                        body=_(f"Error reindexing collection: {str(e)}"),
                        message_type="error",
                    )
            else:
                # For collections without a store, just reset resource states
                ready_docs = collection.resource_ids.filtered(
                    lambda d: d.state == "ready"
                )
                if ready_docs:
                    ready_docs.write({"state": "chunked"})

                    collection.message_post(
                        body=_(
                            f"Reset {len(ready_docs)} resources for re-embedding with model {collection.embedding_model_id.name}."
                        ),
                        message_type="notification",
                    )
                else:
                    collection.message_post(
                        body=_("No resources found to reindex."),
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

    def embed_resources(self, specific_resource_ids=None, batch_size=50):
        """
        Embed all chunked resources using the collection's embedding model and store.

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

            # Ensure we have a store to use
            if not collection.store_id:
                collection.message_post(
                    body=_("No vector store configured for this collection."),
                    message_type="warning",
                )
                continue

            # Ensure the collection exists in the store
            collection._initialize_store()

            # Search for chunks that belong to chunked resources in this collection
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

            embedding_model_id = collection.embedding_model_id.id

            # Process chunks in batches for efficiency
            total_chunks = len(chunks)
            processed_chunks = 0
            processed_resource_ids = (
                set()
            )  # Track which resource IDs had chunks processed

            if not total_chunks:
                message = _("All chunks already have embeddings for the selected model")
                collection.message_post(
                    body=message,
                    message_type="notification",
                )
                continue

            # Process in batches
            for i in range(0, total_chunks, batch_size):
                batch = chunks[i : i + batch_size]

                # Prepare chunked data for the store
                texts = []
                metadata_list = []
                chunk_ids = []

                for chunk in batch:
                    texts.append(chunk.content)
                    metadata = {
                        "resource_id": chunk.resource_id.id,
                        "resource_name": chunk.resource_id.name,
                        "chunk_id": chunk.id,
                        "sequence": chunk.sequence,
                    }
                    # Add custom metadata if present
                    if chunk.metadata:
                        metadata.update(chunk.metadata)

                    metadata_list.append(metadata)
                    chunk_ids.append(chunk.id)
                    processed_resource_ids.add(chunk.resource_id.id)

                try:
                    # Generate embeddings using the collection's embedding model
                    embeddings = collection.embedding_model_id.embedding(texts)
                    # TODO: should it belong here?
                    # Create chunk embedding records
                    embedding_vals_list = []
                    for _i, (chunk_id, vector) in enumerate(
                        zip(chunk_ids, embeddings)
                    ):
                        embedding_vals_list.append(
                            {
                                "chunk_id": chunk_id,
                                "embedding_model_id": embedding_model_id,
                                "embedding": vector,
                            }
                        )
                    # Insert vectors into the store
                    collection.insert_vectors(
                        vectors=embeddings, metadata=metadata_list, ids=chunk_ids
                    )

                    processed_chunks += len(batch)

                    # Commit transaction after each batch to avoid timeout issues
                    self.env.cr.commit()
                except Exception as e:
                    _logger.error(f"Error processing batch: {str(e)}")
                    # Continue with next batch

            # Update resource states to ready - only update resources that had chunks processed
            if processed_resource_ids:
                self.env["llm.resource"].browse(list(processed_resource_ids)).write(
                    {"state": "ready"}
                )
                self.env.cr.commit()

                # Prepare message with resource details for clarity
                doc_count = len(processed_resource_ids)
                msg = _(
                    f"Embedded {processed_chunks} chunks from {doc_count} resources using {collection.embedding_model_id.name}"
                )

                collection.message_post(
                    body=msg,
                    message_type="notification",
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
