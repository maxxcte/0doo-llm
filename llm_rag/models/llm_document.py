import base64
import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

try:
    import pymupdf
except ImportError:
    pymupdf = None

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
        parsers = [
            ("default", "Default Parser"),
        ]
        if pymupdf:  # Only add PDF parser if PyMuPDF is installed
            parsers.append(("pdf", "PDF Parser"))
        return parsers

    @api.model
    def _get_available_chunkers(self):
        """Get all available chunker methods"""
        return [("default", "Default Chunker")]

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

    def _parse_default(self):
        """Default parser implementation - determines file type and calls appropriate parser"""
        self.ensure_one()

        # Get the related record's attachments
        attachments = self.env["ir.attachment"].search(
            [("res_model", "=", "llm.document"), ("res_id", "=", self.id)]
        )

        if not attachments:
            raise UserError(_("No attachments found for document"))

        # For simplicity, we'll use the first attachment
        attachment = attachments[0]

        # Determine file type based on mimetype
        mimetype = attachment.mimetype or "application/octet-stream"

        if mimetype == "application/pdf":
            return self._parse_pdf(attachment)
        elif mimetype.startswith("text/"):
            return self._parse_text(attachment)
        else:
            raise UserError(_("Unsupported file type: %s") % mimetype)

    def _parse_pdf(self, attachment):
        """Parse PDF file and extract text and images"""
        if not pymupdf:
            raise UserError(
                _(
                    "PyMuPDF library is not installed. Please install it to parse PDF files."
                )
            )

        try:
            # Decode attachment data
            pdf_data = base64.b64decode(attachment.datas)

            # Open PDF using PyMuPDF
            text_content = []
            image_count = 0

            # Create a BytesIO object from the PDF data
            with pymupdf.open(stream=pdf_data, filetype="pdf") as doc:
                # Process each page
                for page_num in range(doc.page_count):
                    page = doc[page_num]

                    # Extract text
                    text = page.get_text()
                    text_content.append(f"## Page {page_num + 1}\n\n{text}")

                    # Extract images
                    image_list = page.get_images(full=True)
                    for img_index, img in enumerate(image_list):
                        xref = img[0]
                        try:
                            base_image = doc.extract_image(xref)
                            if base_image:
                                # Store image as attachment
                                image_data = base_image["image"]
                                image_ext = base_image["ext"]
                                image_name = f"image_{page_num}_{img_index}.{image_ext}"

                                # Create attachment for the image
                                img_attachment = self.env["ir.attachment"].create(
                                    {
                                        "name": image_name,
                                        "datas": base64.b64encode(image_data),
                                        "res_model": "llm.document",
                                        "res_id": self.id,
                                        "mimetype": f"image/{image_ext}",
                                    }
                                )

                                # Add image reference to markdown content
                                if img_attachment:
                                    image_url = f"/web/image/{img_attachment.id}"
                                    text_content.append(
                                        f"\n![{image_name}]({image_url})\n"
                                    )
                                    image_count += 1
                        except Exception as e:
                            self._post_message(
                                f"Error extracting image: {str(e)}", "warning"
                            )

            # Join all content
            final_content = "\n\n".join(text_content)

            # Update document with extracted content
            self.content = final_content

            # Post success message
            self._post_message(
                f"Successfully extracted content from document ({doc.page_count} pages, {image_count} images)",
                "success",
            )

            return True

        except Exception as e:
            raise UserError(_("Error parsing PDF: %s") % str(e)) from e

    def _parse_text(self, attachment):
        """Parse plain text file"""
        try:
            # Decode attachment data
            text_data = base64.b64decode(attachment.datas).decode("utf-8")

            # Format as markdown
            self.content = text_data

            # Post success message
            self._post_message(
                "Successfully extracted text content from document", "success"
            )
            return True

        except Exception as e:
            raise UserError(_("Error parsing text file: %s") % str(e)) from e

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
                    document._post_message(
                        f"Error retrieving document: {str(e)}", "error"
                    )
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
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
                    # Use appropriate parser based on selection
                    if document.parser == "default":
                        document._parse_default()
                    elif document.parser == "pdf":
                        # Get the related record's attachments
                        attachments = self.env["ir.attachment"].search(
                            [
                                ("res_model", "=", "llm.document"),
                                ("res_id", "=", document.id),
                            ]
                        )
                        if attachments:
                            document._parse_pdf(attachments[0])
                        else:
                            raise UserError(_("No PDF attachment found"))
                    else:
                        _logger.warning(
                            "Unknown parser %s, falling back to default",
                            document.parser,
                        )
                        document._parse_default()

                    # Mark as parsed
                    document.write({"state": "parsed"})

                except Exception as e:
                    document._post_message(f"Error parsing document: {str(e)}", "error")
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
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
                    document._post_message(
                        f"Error chunking document: {str(e)}", "error"
                    )
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
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
