import base64
import logging
import re

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
    target_chunk_size = fields.Integer(
        string="Target Chunk Size",
        default=512,
        required=True,
        help="Target size of chunks in tokens",
        tracking=True,
    )
    target_chunk_overlap = fields.Integer(
        string="Chunk Overlap",
        default=50,
        required=True,
        help="Number of tokens to overlap between chunks",
        tracking=True,
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
                        success = document._parse_default()
                    elif document.parser == "pdf":
                        # Get the related record's attachments
                        attachments = self.env["ir.attachment"].search(
                            [
                                ("res_model", "=", "llm.document"),
                                ("res_id", "=", document.id),
                            ]
                        )
                        if attachments:
                            success = document._parse_pdf(attachments[0])
                        else:
                            raise UserError(_("No PDF attachment found"))
                    else:
                        _logger.warning(
                            "Unknown parser %s, falling back to default",
                            document.parser,
                        )
                        success = document._parse_default()

                    # Only update state if parsing was successful
                    if success:
                        # Debug logging
                        _logger.info("Parsing successful for document %s, updating state to 'parsed'", document.id)

                        # Explicitly commit the state change to ensure it's saved
                        document.write({"state": "parsed"})
                        self.env.cr.commit()  # Force commit the transaction

                        document._post_message(
                            "Document successfully parsed",
                            "success"
                        )
                    else:
                        document._post_message(
                            "Parsing completed but did not return success",
                            "warning"
                        )

                except Exception as e:
                    _logger.error("Error parsing document %s: %s", document.id, str(e), exc_info=True)
                    document._post_message(f"Error parsing document: {str(e)}", "error")
                    document._unlock()

            # Unlock all successfully processed documents
            documents._unlock()
            return True

        except Exception as e:
            documents._unlock()
            raise UserError(_("Error in batch parsing: %s") % str(e)) from e
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

    def _chunk_default(self):
        """
        Default implementation for splitting document into chunks.
        Uses a simple sentence-based splitting approach.
        """
        self.ensure_one()

        if not self.content:
            raise UserError(_("No content to chunk"))

        # Delete existing chunks
        self.chunk_ids.unlink()

        # Get chunking parameters
        chunk_size = self.target_chunk_size
        chunk_overlap = min(
            self.target_chunk_overlap, chunk_size // 2
        )  # Ensure overlap is not too large

        # Split content into sentences (simple regex-based approach)
        # Note: for a more sophisticated approach, consider using a NLP library
        sentences = re.split(r"(?<=[.!?])\s+", self.content)

        # Function to estimate token count (approximation)
        def estimate_tokens(text):
            # Simple approximation: 1 token ≈ 4 characters for English text
            return len(text) // 4

        # Create chunks using a sliding window approach
        chunks = []
        current_chunk = []
        current_size = 0

        for _i, sentence in enumerate(sentences):
            sentence_tokens = estimate_tokens(sentence)

            # If a single sentence exceeds chunk size, we have to include it anyway
            if current_size + sentence_tokens > chunk_size and current_chunk:
                # Create a chunk from accumulated sentences
                chunk_text = " ".join(current_chunk)
                chunk_seq = len(chunks) + 1

                # Create chunk record - metadata is now computed automatically
                chunk = self.env["llm.document.chunk"].create(
                    {
                        "document_id": self.id,
                        "sequence": chunk_seq,
                        "content": chunk_text,
                    }
                )
                chunks.append(chunk)

                # Handle overlap: keep some sentences for the next chunk
                overlap_tokens = 0
                overlap_sentences = []

                # Work backwards through current_chunk to build overlap
                for sent in reversed(current_chunk):
                    sent_tokens = estimate_tokens(sent)
                    if overlap_tokens + sent_tokens <= chunk_overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_tokens += sent_tokens
                    else:
                        break

                # Start new chunk with overlap sentences
                current_chunk = overlap_sentences
                current_size = overlap_tokens

            # Add current sentence to the chunk
            current_chunk.append(sentence)
            current_size += sentence_tokens

        # Don't forget the last chunk if there's anything left
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunk_seq = len(chunks) + 1

            # Create chunk record - metadata is now computed automatically
            chunk = self.env["llm.document.chunk"].create(
                {
                    "document_id": self.id,
                    "sequence": chunk_seq,
                    "content": chunk_text,
                }
            )
            chunks.append(chunk)

        # Post success message
        self._post_message(
            f"Created {len(chunks)} chunks (target size: {chunk_size}, overlap: {chunk_overlap})",
            "success",
        )

        return len(chunks) > 0
    # Update the chunk method in the LLMDocument model class to use the chunker selection
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
                    # Use appropriate chunker based on selection
                    success = False
                    if document.chunker == "default":
                        success = document._chunk_default()
                    else:
                        _logger.warning(
                            "Unknown chunker %s, falling back to default",
                            document.chunker,
                        )
                        success = document._chunk_default()

                    if success:
                        # Mark as chunked
                        document.write({"state": "chunked"})
                    else:
                        document._post_message(
                            "Failed to create chunks - no content or empty result",
                            "warning",
                        )

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
