import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMKnowledgeChunker(models.Model):
    _inherit = "llm.resource"

    # Chunking configuration fields
    chunker = fields.Selection(
        selection="_get_available_chunkers",
        string="Chunker",
        default="default",
        required=True,
        help="Method used to chunk resource content",
        tracking=True,
    )
    target_chunk_size = fields.Integer(
        string="Target Chunk Size",
        default=200,
        required=True,
        help="Target size of chunks in tokens",
        tracking=True,
    )
    target_chunk_overlap = fields.Integer(
        string="Chunk Overlap",
        default=20,
        required=True,
        help="Number of tokens to overlap between chunks",
        tracking=True,
    )
    state = fields.Selection(
        selection_add=[
            ("chunked", "Chunked"),
            ("ready", "Ready"),
        ],
    )
    chunk_ids = fields.One2many(
        "llm.knowledge.chunk",
        "resource_id",
        string="Chunks",
    )
    chunk_count = fields.Integer(
        string="Chunk Count",
        compute="_compute_chunk_count",
        store=True,
    )
    collection_ids = fields.Many2many(
        "llm.knowledge.collection",
        relation="llm_knowledge_resource_collection_rel",
        column1="resource_id",
        column2="collection_id",
        string="Collections",
    )

    @api.model
    def _get_available_chunkers(self):
        """Get all available chunker methods"""
        return [("default", "Default Chunker")]

    @api.depends("chunk_ids")
    def _compute_chunk_count(self):
        for record in self:
            record.chunk_count = len(record.chunk_ids)

    def action_view_chunks(self):
        """Open a view with all chunks for this resource"""
        self.ensure_one()
        return {
            "name": _("Resource Chunks"),
            "view_mode": "tree,form",
            "res_model": "llm.knowledge.chunk",
            "domain": [("resource_id", "=", self.id)],
            "type": "ir.actions.act_window",
            "context": {"default_resource_id": self.id},
        }

    def chunk(self):
        """Split the document into chunks"""
        for resource in self:
            if resource.state != "parsed":
                _logger.warning(
                    "Resource %s must be in parsed state to create chunks", resource.id
                )
                continue

        # Lock resources and process only the successfully locked ones
        resources = self._lock()
        if not resources:
            return False

        try:
            # Process each resource
            for resource in resources:
                try:
                    # Use appropriate chunker based on selection
                    success = False
                    if resource.chunker == "default":
                        success = resource._chunk_default()
                    else:
                        _logger.warning(
                            "Unknown chunker %s, falling back to default",
                            resource.chunker,
                        )
                        success = resource._chunk_default()

                    if success:
                        # Mark as chunked
                        resource.write({"state": "chunked"})
                    else:
                        resource._post_styled_message(
                            "Failed to create chunks - no content or empty result",
                            "warning",
                        )

                except Exception as e:
                    resource._post_styled_message(
                        f"Error chunking resource: {str(e)}", "error"
                    )
                    resource._unlock()

            # Unlock all successfully processed resources
            resources._unlock()
            return True

        except Exception as e:
            resources._unlock()
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

                # Create chunk record
                chunk = self.env["llm.knowledge.chunk"].create(
                    {
                        "resource_id": self.id,
                        "sequence": chunk_seq,
                        "content": chunk_text,
                        # Note: No need to set collection_ids as it's a related field
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

            # Create chunk record
            chunk = self.env["llm.knowledge.chunk"].create(
                {
                    "resource_id": self.id,
                    "sequence": chunk_seq,
                    "content": chunk_text,
                    # Note: No need to set collection_ids as it's a related field
                }
            )
            chunks.append(chunk)

        # Post success message
        self._post_styled_message(
            f"Created {len(chunks)} chunks (target size: {chunk_size}, overlap: {chunk_overlap})",
            "success",
        )

        return len(chunks) > 0

    def process_resource(self):
        """
        Override the process_resource method to include chunking and embedding steps
        """
        # Call the original process_resource to handle retrieval and parsing
        super().process_resource()

        # Process chunking and embedding
        inconsistent_docs = self.filtered(
            lambda d: d.state in ["chunked", "ready"] and not d.chunk_ids
        )

        if inconsistent_docs:
            inconsistent_docs.write({"state": "parsed"})

        # Process chunks for parsed documents
        parsed_docs = self.filtered(lambda d: d.state == "parsed")
        if parsed_docs:
            parsed_docs.chunk()

        # Embed chunked documents
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
        """Reindex a single resource's chunks"""
        self.ensure_one()

        # Get all collections this resource belongs to
        collections = self.collection_ids
        if not collections:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Reindexing"),
                    "message": _("Resource does not belong to any collections."),
                    "type": "warning",
                },
            }

        # Get all chunks for this resource
        chunks = self.chunk_ids
        if not chunks:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Reindexing"),
                    "message": _("No chunks found for this resource."),
                    "type": "warning",
                },
            }

        # Set resource back to chunked state to trigger re-embedding
        self.write({"state": "chunked"})

        # Delete chunks from each collection's store
        for collection in collections:
            if collection.store_id:
                # Remove chunks from this resource from the store
                try:
                    collection.delete_vectors(ids=chunks.ids)
                except Exception as e:
                    _logger.warning(
                        f"Error removing vectors for chunks from collection {collection.id}: {str(e)}"
                    )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Reindexing"),
                "message": _(
                    f"Reset resource for re-embedding in {len(collections)} collections."
                ),
                "type": "success",
            },
        }

    def action_mass_reindex(self):
        """Reindex multiple resources at once"""
        collections = self.env["llm.knowledge.collection"]
        for resource in self:
            # Add to collections set
            collections |= resource.collection_ids

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

    def embed(self):
        """
        Embed resource chunks in collections by calling the collection's embed_resources method.
        Called after chunking to create vector representations.

        Returns:
            bool: True if any resources were successfully embedded, False otherwise
        """
        # Filter to only get resources in chunked state
        chunked_docs = self.filtered(lambda d: d.state == "chunked")

        if not chunked_docs:
            return False

        # Get all collections for these resources
        collections = self.env["llm.knowledge.collection"]
        for doc in chunked_docs:
            collections |= doc.collection_ids

        # If no collections, resources can't be embedded
        if not collections:
            return False

        # Track if any resources were embedded
        any_embedded = False

        # Let each collection handle the embedding
        for collection in collections:
            result = collection.embed_resources(specific_resource_ids=chunked_docs.ids)
            # Check if result is not None before trying to access .get()
            if (
                result
                and result.get("success")
                and result.get("processed_resources", 0) > 0
            ):
                any_embedded = True

        # Return True only if resources were actually embedded
        return any_embedded

    @api.model
    def action_mass_process_resources(self):
        """
        Server action handler for mass processing resources.
        This will be triggered from the server action in the UI.
        """
        active_ids = self.env.context.get("active_ids", [])
        if not active_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Resources Selected"),
                    "message": _("Please select resources to process."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        resources = self.browse(active_ids)
        # Process all selected resources
        resources.process_resource()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Resource Processing"),
                "message": _("%s resources processing started") % len(resources),
                "sticky": False,
                "type": "success",
            },
        }
