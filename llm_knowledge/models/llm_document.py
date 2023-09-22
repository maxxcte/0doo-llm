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
        """Process the document through the entire pipeline"""
        for document in self:
            if document.state == "draft":
                document.retrieve()

            if document.state == "retrieved":
                document.parse()

            if document.state == "parsed":
                document.chunk()

            # After chunking, check if document belongs to collections
            if document.state == "chunked":
                collections = document.collection_ids
                if collections:
                    # Notify user about embedding through collections
                    document._post_message(
                        f"Document is ready to be embedded through its collections "
                        f"({', '.join(collections.mapped('name'))}). "
                        f"Please use the 'Embed Documents' function in the collection.",
                        "info",
                    )
                else:
                    document._post_message(
                        "Document is chunked but not part of any collection. "
                        "Add it to a collection and use 'Embed Documents' to complete processing.",
                        "warning",
                    )

        return True

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
