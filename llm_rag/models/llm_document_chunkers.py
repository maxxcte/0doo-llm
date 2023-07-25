import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMDocumentChunker(models.Model):
    _inherit = "llm.document"

    # Chunking configuration fields
    chunker = fields.Selection(
        selection="_get_available_chunkers",
        string="Chunker",
        default="default",
        required=True,
        help="Method used to chunk document content",
        tracking=True,
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

    @api.model
    def _get_available_chunkers(self):
        """Get all available chunker methods"""
        return [("default", "Default Chunker")]

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
