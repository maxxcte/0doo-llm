import logging

import numpy as np

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class RAGSearchWizard(models.TransientModel):
    _name = "llm.rag.search.wizard"
    _description = "RAG Search Wizard"

    # Fields
    query = fields.Text(
        string="Search Query",
        required=True,
        help="Enter your search query here",
    )
    top_k = fields.Integer(
        string="Top K Chunks",
        default=5,
        help="Number of chunks to retrieve per document",
    )
    top_n = fields.Integer(
        string="Top N Documents",
        default=3,
        help="Total number of documents to retrieve",
    )
    similarity_cutoff = fields.Float(
        string="Similarity Cutoff",
        default=0.7,
        help="Minimum similarity score (0-1) for results",
    )
    state = fields.Selection(
        [("search", "Search"), ("results", "Results")],
        default="search",
        required=True,
    )
    result_ids = fields.Many2many(
        "llm.document.chunk",
        string="Search Results",
        readonly=True,
    )
    result_lines = fields.One2many(
        "llm.rag.search.result.line",
        "wizard_id",
        string="Result Lines",
    )

    # Computed Fields
    result_count = fields.Integer(
        compute="_compute_result_count",
        string="Result Count",
    )

    @api.depends("result_ids")
    def _compute_result_count(self):
        for wizard in self:
            wizard.result_count = len(wizard.result_ids)

    # Helper Methods
    def _get_embedding_model(self):
        """Retrieve an embedding model or raise an error."""
        model = self.env["llm.model"].search([("model_use", "=", "embedding")], limit=1)
        if not model:
            self._raise_error(
                "No Embedding Model", "Please configure an embedding model."
            )
        return model

    def _get_query_vector(self, embedding_model):
        """Generate query embedding vector."""
        try:
            embedding = embedding_model.embedding(self.query.strip())
            return (
                np.array(embedding, dtype=np.float32)
                if isinstance(embedding, list)
                else embedding
            )
        except Exception as e:
            self._raise_error(
                "Embedding Error", f"Failed to generate embedding: {str(e)}"
            )

    def _build_search_sql(self, domain):
        """Build SQL query for vector search."""
        sql = """
            SELECT ch.id, ch.document_id, 1 - (ch.embedding <=> %s) AS similarity
            FROM llm_document_chunk ch
            JOIN llm_document doc ON ch.document_id = doc.id
            WHERE ch.embedding IS NOT NULL
        """
        params = [None]  # Placeholder for vector
        if domain:
            if domain[0][0] == "document_id.id" and domain[0][1] == "in":
                sql += " AND doc.id IN %s"
                params.append(tuple(domain[0][2]))
        sql += " AND 1 - (ch.embedding <=> %s) >= %s ORDER BY similarity DESC LIMIT %s"
        return sql, params

    def _raise_error(self, title, message, message_type="warning"):
        """Raise a user-friendly error notification."""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _(title),
                "message": _(message),
                "type": message_type,
                "sticky": False,
            },
        }

    def _return_wizard(self):
        """Return action to reopen the wizard."""
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    # Main Action
    def action_search(self):
        """Execute vector search with the query."""
        self.ensure_one()
        _logger.debug(f"Search query: {self.query}")

        # Get domain from context
        active_ids = self.env.context.get("active_ids", [])
        domain = [("document_id.id", "in", active_ids)] if active_ids else []

        # Get embedding and vector
        embedding_model = self._get_embedding_model()
        query_vector = self._get_query_vector(embedding_model)
        pg_vector = (
            f"[{','.join(map(str, query_vector.tolist()))}]"
            if isinstance(query_vector, np.ndarray)
            else query_vector
        )

        # Prepare and execute SQL
        from pgvector.psycopg2 import register_vector

        register_vector(self.env.cr)
        sql, params = self._build_search_sql(domain)
        params[0] = pg_vector  # Set vector
        params.extend([pg_vector, self.similarity_cutoff, self.top_n * self.top_k])
        self.env.cr.execute(sql, params)

        # Process results
        results = self.env.cr.fetchall()
        chunk_ids, result_lines, doc_chunk_count, processed_docs = [], [], {}, set()
        for chunk_id, doc_id, similarity in results:
            doc_chunk_count.setdefault(doc_id, 0)
            if doc_id in processed_docs and doc_chunk_count[doc_id] >= self.top_k:
                continue
            chunk_ids.append(chunk_id)
            doc_chunk_count[doc_id] += 1
            result_lines.append(
                (0, 0, {"chunk_id": chunk_id, "similarity": similarity})
            )
            if doc_chunk_count[doc_id] >= self.top_k:
                processed_docs.add(doc_id)
            if len(processed_docs) >= self.top_n and all(
                c >= self.top_k for c in doc_chunk_count.values()
            ):
                break

        # Update wizard
        self.write(
            {
                "state": "results",
                "result_ids": [(6, 0, chunk_ids)],
                "result_lines": result_lines,
            }
        )
        return self._return_wizard()

    def action_back_to_search(self):
        """Reset to search state."""
        self.ensure_one()
        self.write(
            {"state": "search", "result_ids": [(5, 0, 0)], "result_lines": [(5, 0, 0)]}
        )
        return self._return_wizard()


class RAGSearchResultLine(models.TransientModel):
    _name = "llm.rag.search.result.line"
    _description = "RAG Search Result Line"
    _order = "similarity desc"

    wizard_id = fields.Many2one(
        "llm.rag.search.wizard", required=True, ondelete="cascade"
    )
    chunk_id = fields.Many2one("llm.document.chunk", required=True, readonly=True)
    document_id = fields.Many2one(
        related="chunk_id.document_id", store=True, readonly=True
    )
    document_name = fields.Char(related="document_id.name", readonly=True)
    chunk_name = fields.Char(related="chunk_id.name", readonly=True)
    content = fields.Text(related="chunk_id.content", readonly=True)
    similarity = fields.Float(digits=(5, 4), readonly=True)
    similarity_percentage = fields.Char(compute="_compute_similarity_percentage")

    @api.depends("similarity")
    def _compute_similarity_percentage(self):
        for line in self:
            line.similarity_percentage = f"{line.similarity * 100:.2f}%"
