import logging

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

try:
    from llama_index.core import Document as LlamaDocument
    from llama_index.core.node_parser import (
        HierarchicalNodeParser,
        MarkdownNodeParser,
        SentenceSplitter,
        SentenceWindowNodeParser,
        TokenTextSplitter,
    )

    HAS_LLAMA_INDEX = True
except ImportError:
    _logger.warning("Could not import llama_index, make sure it is installed.")
    HAS_LLAMA_INDEX = False


class LLMDocumentLlamaChunker(models.Model):
    _inherit = "llm.document"

    @api.model
    def _get_available_chunkers(self):
        """
        Extend the available chunkers to include LlamaIndex's chunkers.
        """
        chunkers = super()._get_available_chunkers()
        chunkers.extend(
            [
                ("llama_markdown", "LlamaIndex Markdown Chunker"),
                ("llama_sentence", "LlamaIndex Sentence Splitter"),
                ("llama_token", "LlamaIndex Token Splitter"),
                ("llama_hierarchical", "LlamaIndex Hierarchical Chunker"),
            ]
        )
        return chunkers

    @api.model
    def default_get(self, fields_list):
        """
        Override default_get to set the default chunker to llama_markdown if LlamaIndex is installed.
        """
        res = super().default_get(fields_list)

        if "chunker" in fields_list and HAS_LLAMA_INDEX:
            res["chunker"] = "llama_markdown"

        return res

    def _chunk_llama_markdown(self):
        """
        LlamaIndex Markdown-aware chunker that respects markdown structure.
        This is particularly useful since llm.document content is always in markdown format.
        """
        self.ensure_one()

        if not HAS_LLAMA_INDEX:
            raise UserError(
                _(
                    "LlamaIndex is not installed. Please install it with pip: pip install llama_index"
                )
            )

        if not self.content:
            raise UserError(_("No content to chunk"))

        # Delete existing chunks
        self.chunk_ids.unlink()

        # Create a LlamaIndex document from the content
        llama_doc = LlamaDocument(
            text=self.content,
            metadata={
                "name": self.name,
                "res_model": self.res_model,
                "res_id": self.res_id,
            },
        )

        # Use the MarkdownNodeParser
        parser = MarkdownNodeParser()
        nodes = parser.get_nodes_from_documents([llama_doc])

        # Create chunks from the parsed nodes
        created_chunks = []
        for idx, node in enumerate(nodes, 1):
            chunk = self.env["llm.document.chunk"].create(
                {
                    "document_id": self.id,
                    "sequence": idx,
                    "content": node.text,
                    "metadata": {
                        **node.metadata,
                        "start_char_idx": node.start_char_idx,
                        "end_char_idx": node.end_char_idx,
                    }
                    if hasattr(node, "metadata")
                    else {},
                }
            )
            created_chunks.append(chunk)

        # Post success message
        self._post_message(
            f"Created {len(created_chunks)} chunks using LlamaIndex MarkdownNodeParser",
            "success",
        )

        return len(created_chunks) > 0

    def _chunk_llama_sentence(self):
        """
        LlamaIndex sentence-based chunker with customizable chunk size and overlap.
        """
        self.ensure_one()

        if not HAS_LLAMA_INDEX:
            raise UserError(
                _(
                    "LlamaIndex is not installed. Please install it with pip: pip install llama_index"
                )
            )

        if not self.content:
            raise UserError(_("No content to chunk"))

        # Delete existing chunks
        self.chunk_ids.unlink()

        # Create a LlamaIndex document
        llama_doc = LlamaDocument(
            text=self.content,
            metadata={
                "name": self.name,
                "res_model": self.res_model,
                "res_id": self.res_id,
            },
        )

        # Use SentenceSplitter with the configured chunk sizes
        splitter = SentenceSplitter(
            chunk_size=self.target_chunk_size,
            chunk_overlap=self.target_chunk_overlap,
        )
        nodes = splitter.get_nodes_from_documents([llama_doc])

        # Create chunks
        created_chunks = []
        for idx, node in enumerate(nodes, 1):
            chunk = self.env["llm.document.chunk"].create(
                {
                    "document_id": self.id,
                    "sequence": idx,
                    "content": node.text,
                    "metadata": {
                        **node.metadata,
                        "start_char_idx": getattr(node, "start_char_idx", None),
                        "end_char_idx": getattr(node, "end_char_idx", None),
                    }
                    if hasattr(node, "metadata")
                    else {},
                }
            )
            created_chunks.append(chunk)

        # Post success message
        self._post_message(
            f"Created {len(created_chunks)} chunks using LlamaIndex SentenceSplitter "
            f"(size: {self.target_chunk_size}, overlap: {self.target_chunk_overlap})",
            "success",
        )

        return len(created_chunks) > 0

    def _chunk_llama_token(self):
        """
        LlamaIndex token-based chunker for precise token-count chunking.
        """
        self.ensure_one()

        if not HAS_LLAMA_INDEX:
            raise UserError(
                _(
                    "LlamaIndex is not installed. Please install it with pip: pip install llama_index"
                )
            )

        if not self.content:
            raise UserError(_("No content to chunk"))

        # Delete existing chunks
        self.chunk_ids.unlink()

        # Create a LlamaIndex document
        llama_doc = LlamaDocument(
            text=self.content,
            metadata={
                "name": self.name,
                "res_model": self.res_model,
                "res_id": self.res_id,
            },
        )

        # Use TokenTextSplitter with the configured chunk sizes
        splitter = TokenTextSplitter(
            chunk_size=self.target_chunk_size,
            chunk_overlap=self.target_chunk_overlap,
        )
        nodes = splitter.get_nodes_from_documents([llama_doc])

        # Create chunks
        created_chunks = []
        for idx, node in enumerate(nodes, 1):
            chunk = self.env["llm.document.chunk"].create(
                {
                    "document_id": self.id,
                    "sequence": idx,
                    "content": node.text,
                    "metadata": {
                        **node.metadata,
                        "start_char_idx": getattr(node, "start_char_idx", None),
                        "end_char_idx": getattr(node, "end_char_idx", None),
                    }
                    if hasattr(node, "metadata")
                    else {},
                }
            )
            created_chunks.append(chunk)

        # Post success message
        self._post_message(
            f"Created {len(created_chunks)} chunks using LlamaIndex TokenTextSplitter "
            f"(size: {self.target_chunk_size}, overlap: {self.target_chunk_overlap})",
            "success",
        )

        return len(created_chunks) > 0

    def _chunk_llama_hierarchical(self):
        """
        LlamaIndex hierarchical chunker that creates nested chunks at multiple levels of granularity.
        """
        self.ensure_one()

        if not HAS_LLAMA_INDEX:
            raise UserError(
                _(
                    "LlamaIndex is not installed. Please install it with pip: pip install llama_index"
                )
            )

        if not self.content:
            raise UserError(_("No content to chunk"))

        # Delete existing chunks
        self.chunk_ids.unlink()

        # Create a LlamaIndex document
        llama_doc = LlamaDocument(
            text=self.content,
            metadata={
                "name": self.name,
                "res_model": self.res_model,
                "res_id": self.res_id,
            },
        )

        # Use HierarchicalNodeParser
        # We'll use chunk sizes of 2048, 512, and 128 tokens
        chunk_sizes = [2048, 512, 128]
        parser = HierarchicalNodeParser.from_defaults(chunk_sizes=chunk_sizes)
        nodes = parser.get_nodes_from_documents([llama_doc])

        # Create chunks
        created_chunks = []
        for idx, node in enumerate(nodes, 1):
            chunk = self.env["llm.document.chunk"].create(
                {
                    "document_id": self.id,
                    "sequence": idx,
                    "content": node.text,
                    "metadata": {
                        **node.metadata,
                        "start_char_idx": getattr(node, "start_char_idx", None),
                        "end_char_idx": getattr(node, "end_char_idx", None),
                        "hierarchical_level": getattr(node, "level", 0),
                    }
                    if hasattr(node, "metadata")
                    else {},
                }
            )
            created_chunks.append(chunk)

        # Post success message
        self._post_message(
            f"Created {len(created_chunks)} hierarchical chunks using LlamaIndex "
            f"HierarchicalNodeParser with sizes {chunk_sizes}",
            "success",
        )

        return len(created_chunks) > 0

    def chunk(self):
        """Override to add LlamaIndex chunking methods"""
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
                    success = False

                    # Use the appropriate chunker based on selection
                    if document.chunker == "llama_markdown":
                        success = document._chunk_llama_markdown()
                    elif document.chunker == "llama_sentence":
                        success = document._chunk_llama_sentence()
                    elif document.chunker == "llama_token":
                        success = document._chunk_llama_token()
                    elif document.chunker == "llama_hierarchical":
                        success = document._chunk_llama_hierarchical()
                    else:
                        # Fall back to original chunking methods
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
            raise UserError(_("Error in batch chunking: %s") % str(e))
