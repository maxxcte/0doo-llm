import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

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
    embedding_model = fields.Char(
        string="Embedding Model",
        tracking=True,
        help="The model used to create embeddings for this document",
    )

    # New selection fields for the RAG pipeline components
    retriever = fields.Selection(
        selection="_get_available_retrievers",
        string="Retriever",
        default="default",
        required=True,
        help="Method used to retrieve document content",
        tracking=True,
    )
    parser = fields.Selection(
        selection="_get_available_parsers",
        string="Parser",
        default="default",
        required=True,
        help="Method used to parse document content",
        tracking=True,
    )
    chunker = fields.Selection(
        selection="_get_available_chunkers",
        string="Chunker",
        default="default",
        required=True,
        help="Method used to chunk document content",
        tracking=True,
    )

    @api.depends("chunk_ids")
    def _compute_chunk_count(self):
        for record in self:
            record.chunk_count = len(record.chunk_ids)

    @api.depends("lock_date")
    def _compute_kanban_state(self):
        for record in self:
            record.kanban_state = "blocked" if record.lock_date else "normal"

    @api.model
    def _get_available_retrievers(self):
        """Get all available retriever methods"""
        return [("default", "Default Retriever")]

    @api.model
    def _get_available_parsers(self):
        """Get all available parser methods"""
        return [("default", "Default Parser")]

    @api.model
    def _get_available_chunkers(self):
        """Get all available chunker methods"""
        return [("default", "Default Chunker")]

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

    def retrieve(self):
        """Retrieve document content from the related record"""
        for document in self:
            if document.state != "draft":
                _logger.warning(
                    "Document %s must be in draft state to retrieve content",
                    document.id,
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
                    # Get the related record
                    record = self.env[document.res_model].browse(document.res_id)
                    if not record.exists():
                        raise UserError(_("Referenced record not found"))

                    # Call the rag_retrieve method on the record if it exists
                    if hasattr(record, "rag_retrieve"):
                        record.rag_retrieve(document)

                    # Mark as retrieved
                    document.write({"state": "retrieved"})

                except Exception as e:
                    _logger.error(
                        "Error retrieving document %s: %s", document.id, str(e)
                    )
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
            _logger.error("Error in batch retrieval: %s", str(e))
            raise UserError(_("Error in batch retrieval: %s") % str(e)) from e

    def parse(self):
        """Parse the retrieved content to markdown"""
        for document in self:
            if document.state != "retrieved":
                _logger.warning(
                    "Document %s must be in retrieved state to parse content",
                    document.id,
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
                    # Placeholder for actual implementation
                    # Will be replaced by specific parser implementations in extending modules

                    # Mark as parsed
                    document.write({"state": "parsed"})

                except Exception as e:
                    _logger.error("Error parsing document %s: %s", document.id, str(e))
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
            _logger.error("Error in batch parsing: %s", str(e))
            raise UserError(_("Error in batch parsing: %s") % str(e)) from e

    def chunk(self):
        """Split the document into chunks"""
        for document in self:
            if document.state != "parsed":
                _logger.warning(
                    "Document %s must be in parsed state to create chunks", document.id
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
                    # Placeholder for actual implementation
                    # Will be replaced by specific chunker implementations in extending modules

                    # Mark as chunked
                    document.write({"state": "chunked"})

                except Exception as e:
                    _logger.error("Error chunking document %s: %s", document.id, str(e))
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
            _logger.error("Error in batch chunking: %s", str(e))
            raise UserError(_("Error in batch chunking: %s") % str(e)) from e

    def embed(self):
        """Embed the document chunks"""
        for document in self:
            if document.state != "chunked":
                _logger.warning(
                    "Document %s must be in chunked state to embed", document.id
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
                    # Placeholder for actual implementation

                    # Mark as ready
                    document.write({"state": "ready"})

                except Exception as e:
                    _logger.error(
                        "Error embedding document %s: %s", document.id, str(e)
                    )
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
            _logger.error("Error in batch embedding: %s", str(e))
            raise UserError(_("Error in batch embedding: %s") % str(e)) from e

    def process_document(self):
        """Process the document through the entire pipeline"""
        for document in self:
            if document.state == "draft":
                document.retrieve()

            if document.state == "retrieved":
                document.parse()

            if document.state == "parsed":
                document.chunk()

            if document.state == "chunked":
                document.embed()

        return True

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
