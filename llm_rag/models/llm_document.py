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

    @api.depends("chunk_ids")
    def _compute_chunk_count(self):
        for record in self:
            record.chunk_count = len(record.chunk_ids)

    @api.depends("lock_date")
    def _compute_kanban_state(self):
        for record in self:
            record.kanban_state = "blocked" if record.lock_date else "normal"

    def retrieve(self):
        """
        Retrieve the document content from the related model.
        This calls the rag_retrieve method on the related model.
        Each model can implement its own rag_retrieve method to define
        how its content should be retrieved for RAG.
        """
        self.ensure_one()
        if self.state != "draft":
            raise UserError(_("Document must be in draft state to retrieve content"))

        if self.lock_date:
            raise UserError(_("Document is locked for processing"))

        # Lock the document
        self.write({"lock_date": fields.Datetime.now()})

        try:
            # Get the related record
            record = self.env[self.res_model].browse(self.res_id)
            if not record.exists():
                raise UserError(_("Referenced record not found"))

            # Call the rag_retrieve method on the record if it exists
            # This method should be implemented by each model that wants to support RAG
            if hasattr(record, 'rag_retrieve'):
                record.rag_retrieve(self)

            # Mark as retrieved and unlock
            self.write({
                "state": "retrieved",
                "lock_date": False,
            })

            return True

        except Exception as e:
            self.write({"lock_date": False})
            _logger.error("Error retrieving document: %s", str(e))
            raise UserError(_("Error retrieving document: %s") % str(e))
    def parse(self):
        """
        Parse the retrieved content to markdown
        """
        self.ensure_one()
        if self.state != "retrieved":
            raise UserError(_("Document must be in retrieved state to parse content"))

        if self.lock_date:
            raise UserError(_("Document is locked for processing"))

        # Lock the document
        self.write({"lock_date": fields.Datetime.now()})

        try:
            # TODO: Implement document parsing logic
            # This is a placeholder for the actual implementation

            # Update state after successful parsing
            self.write(
                {
                    "state": "parsed",
                    "lock_date": False,
                }
            )

            return True

        except Exception as e:
            self.write({"lock_date": False})
            _logger.error("Error parsing document: %s", str(e))
            raise UserError(_("Error parsing document: %s") % str(e))

    def chunk(self):
        """
        Split the document into chunks
        """
        self.ensure_one()
        if self.state != "parsed":
            raise UserError(_("Document must be in parsed state to create chunks"))

        if self.lock_date:
            raise UserError(_("Document is locked for processing"))

        # Lock the document
        self.write({"lock_date": fields.Datetime.now()})

        try:
            # TODO: Implement document chunking logic
            # This is a placeholder for the actual implementation

            # Update state after successful chunking
            self.write(
                {
                    "state": "chunked",
                    "lock_date": False,
                }
            )

            return True

        except Exception as e:
            self.write({"lock_date": False})
            _logger.error("Error chunking document: %s", str(e))
            raise UserError(_("Error chunking document: %s") % str(e))

    def embed(self):
        """
        Embed the document chunks
        """
        self.ensure_one()
        if self.state != "chunked":
            raise UserError(_("Document must be in chunked state to embed"))

        if self.lock_date:
            raise UserError(_("Document is locked for processing"))

        # Lock the document
        self.write({"lock_date": fields.Datetime.now()})

        try:
            # TODO: Implement document embedding logic
            # This is a placeholder for the actual implementation

            # Update state after successful embedding
            self.write(
                {
                    "state": "ready",
                    "lock_date": False,
                }
            )

            return True

        except Exception as e:
            self.write({"lock_date": False})
            _logger.error("Error embedding document: %s", str(e))
            raise UserError(_("Error embedding document: %s") % str(e))

    def process_document(self):
        """
        Process the document through the entire pipeline
        """
        self.ensure_one()

        if self.state == "draft":
            self.retrieve()

        if self.state == "retrieved":
            self.parse()

        if self.state == "parsed":
            self.chunk()

        if self.state == "chunked":
            self.embed()

        return True

    def action_view_chunks(self):
        """
        Open a view with all chunks for this document
        """
        self.ensure_one()
        return {
            "name": _("Document Chunks"),
            "view_mode": "tree,form",
            "res_model": "llm.document.chunk",
            "domain": [("document_id", "=", self.id)],
            "type": "ir.actions.act_window",
            "context": {"default_document_id": self.id},
        }
