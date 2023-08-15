import json
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.tools.safe_eval import safe_eval

_logger = logging.getLogger(__name__)


class LLMDocumentCollection(models.Model):
    _name = "llm.document.collection"
    _description = "Document Collection for RAG"
    _inherit = ["mail.thread", "mail.activity.mixin"]
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
    document_ids = fields.Many2many(
        "llm.document",
        string="Documents",
        relation="llm_document_collection_rel",
        column1="collection_id",
        column2="document_id",
    )
    source_domains = fields.Text(
        string="Source Domains",
        help="JSON structure containing model-domain pairs to select records for RAG document creation",
        tracking=True,
    )
    document_count = fields.Integer(
        string="Document Count",
        compute="_compute_document_count",
        store=True,
    )
    chunk_count = fields.Integer(
        string="Chunk Count",
        compute="_compute_chunk_count",
    )

    @api.depends("document_ids")
    def _compute_document_count(self):
        for record in self:
            record.document_count = len(record.document_ids)

    def _compute_chunk_count(self):
        for record in self:
            chunks = self.env["llm.document.chunk"].search(
                [("collection_ids", "=", record.id)]
            )
            record.chunk_count = len(chunks)

    def action_view_documents(self):
        """Open a view with all documents in this collection"""
        self.ensure_one()
        return {
            "name": _("Collection Documents"),
            "view_mode": "tree,form",
            "res_model": "llm.document",
            "domain": [("id", "in", self.document_ids.ids)],
            "type": "ir.actions.act_window",
            "context": {"default_collection_ids": [(6, 0, [self.id])]},
        }

    def action_view_chunks(self):
        """Open a view with all chunks from documents in this collection"""
        self.ensure_one()

        return {
            "name": _("Collection Chunks"),
            "view_mode": "tree,form",
            "res_model": "llm.document.chunk",
            "domain": [("collection_ids", "=", self.id)],
            "type": "ir.actions.act_window",
        }

    def _parse_source_domains(self):
        """Parse the source_domains field into a dictionary of model:domain pairs"""
        self.ensure_one()
        if not self.source_domains:
            return {}

        try:
            # Parse the JSON structure
            domains_dict = json.loads(self.source_domains)
            return domains_dict
        except json.JSONDecodeError as e:
            raise UserError(_("Invalid JSON format in source domains")) from e

    def add_documents_from_domain(self):
        """
        Add documents to collection by creating llm.document for records matching domains.
        This creates RAG documents for Odoo records from multiple models based on
        the domain criteria defined in source_domains.
        """
        for collection in self:
            if not collection.source_domains:
                collection.message_post(
                    body=_("Please define source domains before adding documents."),
                    message_type="notification",
                )
                continue

            domains_dict = collection._parse_source_domains()
            if not domains_dict:
                continue

            created_count = 0
            linked_count = 0

            # Process each model and its domain
            for model_name, domain_str in domains_dict.items():
                # Validate model exists
                if model_name not in self.env:
                    collection.message_post(
                        body=_(f"Model '{model_name}' not found. Skipping."),
                        message_type="notification",
                    )
                    continue

                # Get model and evaluate domain
                model = self.env[model_name]
                domain = safe_eval(domain_str)

                # Search records matching the domain
                records = model.search(domain)

                if not records:
                    collection.message_post(
                        body=_(
                            f"No records found for model '{model_name}' with given domain."
                        ),
                        message_type="notification",
                    )
                    continue

                # Create or link llm.document for each record
                for record in records:
                    # Check if document already exists for this record
                    existing_doc = self.env["llm.document"].search(
                        [
                            ("res_model", "=", model_name),
                            ("res_id", "=", record.id),
                        ],
                        limit=1,
                    )

                    if existing_doc:
                        # Link existing document to this collection if not already linked
                        if existing_doc.id not in collection.document_ids.ids:
                            collection.write({"document_ids": [(4, existing_doc.id)]})
                            linked_count += 1
                    else:
                        # Create new document and link to collection
                        # Try to get a meaningful name from the record
                        if hasattr(record, "display_name") and record.display_name:
                            name = record.display_name
                        elif hasattr(record, "name") and record.name:
                            name = record.name
                        else:
                            model_display = self.env["ir.model"]._get(model_name).name
                            name = f"{model_display} #{record.id}"

                        new_doc = self.env["llm.document"].create(
                            {
                                "name": name,
                                "res_model": model_name,
                                "res_id": record.id,
                            }
                        )

                        collection.write({"document_ids": [(4, new_doc.id)]})
                        created_count += 1

            # Post summary message
            if created_count > 0 or linked_count > 0:
                collection.message_post(
                    body=_(
                        f"Processing complete: Created {created_count} new documents, linked {linked_count} existing documents."
                    ),
                    message_type="notification",
                )
            elif created_count == 0 and linked_count == 0:
                collection.message_post(
                    body=_("No new documents were created or linked."),
                    message_type="notification",
                )

    def action_open_add_domain_wizard(self):
        """Open wizard to add a domain to the source domains"""
        self.ensure_one()
        return {
            "name": _("Add Domain to Collection"),
            "type": "ir.actions.act_window",
            "res_model": "llm.add.domain.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_collection_id": self.id,
            },
        }

    def process_documents(self):
        """Process documents through retrieval, parsing, and chunking (up to chunked state)"""
        for collection in self:
            draft_docs = collection.document_ids.filtered(lambda d: d.state == "draft")
            retrieved_docs = collection.document_ids.filtered(
                lambda d: d.state == "retrieved"
            )
            parsed_docs = collection.document_ids.filtered(
                lambda d: d.state == "parsed"
            )

            # Process documents through the pipeline stages
            if draft_docs:
                draft_docs.retrieve()

            if retrieved_docs:
                retrieved_docs.parse()

            if parsed_docs:
                parsed_docs.chunk()

            # Count processed documents
            processed = len(draft_docs) + len(retrieved_docs) + len(parsed_docs)

            if processed > 0:
                collection.message_post(
                    body=_(
                        f"Processed {processed} documents through the RAG pipeline."
                    ),
                    message_type="notification",
                )
            else:
                collection.message_post(
                    body=_("No documents needed processing."),
                    message_type="notification",
                )

    def reindex_collection(self):
        """Reindex all documents in the collection"""
        for collection in self:
            # Get all chunks from this collection
            chunks = self.env["llm.document.chunk"].search([
                ("collection_ids", "=", collection.id)
            ])

            if chunks:
                # Create collection-specific index
                dimensions = None
                if collection.embedding_model_id:
                    # Get sample embedding to determine dimensions
                    sample_embedding = collection.embedding_model_id.embedding("")[0]
                    if sample_embedding:
                        dimensions = len(sample_embedding)

                # Use the create_embedding_index method from EmbeddingMixin
                chunks.create_embedding_index(
                    collection_id=collection.id,
                    dimensions=dimensions,
                    force=True  # Force recreate
                )

                collection.message_post(
                    body=_(f"Reindexed {len(chunks)} chunks."),
                    message_type="notification",
                )
            else:
                collection.message_post(
                    body=_("No chunks found to reindex."),
                    message_type="notification",
                )

    def action_process_and_embed(self):
        """Process and embed documents in one action"""
        for collection in self:
            collection.process_documents()
            collection.embed_documents()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Collection Processing"),
                "message": _("Documents processed and embedded successfully."),
                "sticky": False,
                "type": "success",
            },
        }

    def embed_documents(self):
        """Embed all chunked documents using the collection's embedding model"""
        for collection in self:
            if not collection.embedding_model_id:
                raise UserError(
                    _("Embedding model must be specified for the collection")
                )

            # Get all documents in chunked state
            chunked_docs = collection.document_ids.filtered(
                lambda d: d.state == "chunked"
            )

            if not chunked_docs:
                collection.message_post(
                    body=_("No documents in chunked state to embed."),
                    message_type="notification",
                )
                continue

            # Get all chunks from these documents
            chunks = self.env["llm.document.chunk"].search(
                [("document_id", "in", chunked_docs.ids)]
            )

            if not chunks:
                collection.message_post(
                    body=_("No chunks found for documents in chunked state."),
                    message_type="notification",
                )
                continue

            # Apply the collection's embedding model
            embedding_model = collection.embedding_model_id

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
                    chunk.write({
                        "embedding": batch_embeddings[j],
                        "embedding_model_id": embedding_model.id,
                        "collection_ids": [(4, collection.id)]
                    })

                processed_chunks += len(batch)
                _logger.info(f"Processed {processed_chunks}/{total_chunks} chunks")

                # Commit transaction after each batch to avoid timeout issues
                self.env.cr.commit()

            # Update document states to ready
            if processed_chunks > 0:
                chunked_docs.write({"state": "ready"})
                self.env.cr.commit()

                collection.message_post(
                    body=_(
                        f"Embedded {processed_chunks} chunks using {embedding_model.name}"
                    ),
                    message_type="notification",
                )

                # Create a collection-specific index for better performance
                # Call the model-level method, not on the recordset
                dimensions = len(batch_embeddings[0]) if batch_embeddings else None
                self.env["llm.document.chunk"].create_embedding_index(
                    collection_id=collection.id,
                    dimensions=dimensions
                )
            else:
                collection.message_post(
                    body=_("No chunks were successfully embedded"),
                    message_type="warning",
                )