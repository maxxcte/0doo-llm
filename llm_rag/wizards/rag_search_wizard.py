import numpy as np

from odoo import _, api, fields, models


class RAGSearchWizard(models.TransientModel):
    _name = "llm.rag.search.wizard"
    _description = "RAG Search Wizard"

    name = fields.Char(
        string="Name",
        default="RAG Search",
        readonly=True,
    )
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

    # States for the wizard
    state = fields.Selection(
        [
            ("search", "Search"),
            ("results", "Results"),
        ],
        default="search",
    )

    # Fields for the results page
    result_count = fields.Integer(
        string="Result Count",
        compute="_compute_result_count",
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

    @api.depends("result_ids")
    def _compute_result_count(self):
        for wizard in self:
            wizard.result_count = len(wizard.result_ids)

    def action_search(self):
        """Execute the vector search with the given query"""
        self.ensure_one()

        if not self.query or self.query.strip():
            return {
                "type": "ir.actions.act_window",
                "res_model": "llm.rag.search.wizard",
                "res_id": self.id,
                "view_mode": "form",
                "target": "new",
                "context": self.env.context,
            }

        # Get the embedding model from context or use a default one
        active_model = self.env.context.get("active_model")
        active_ids = self.env.context.get("active_ids", [])

        # If no specific model or records are provided, search all documents
        if not active_model or not active_ids:
            domain = []
        else:
            # Search only in the selected documents
            domain = [("document_id.id", "in", active_ids)]

        # Find an embedding model to use
        embedding_model = self.env["llm.model"].search(
            [("model_use", "=", "embedding")], limit=1
        )

        if not embedding_model:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Embedding Model"),
                    "message": _("Please configure at least one embedding model."),
                    "sticky": False,
                    "type": "danger",
                },
            }

        # Get embedding for the query
        try:
            query_embedding = embedding_model.embedding(self.query)
        except Exception as e:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Embedding Error"),
                    "message": _("Failed to generate embedding: %s") % str(e),
                    "sticky": False,
                    "type": "danger",
                },
            }

        # Use pgvector for the search
        from pgvector.psycopg2 import register_vector

        register_vector(self.env.cr)

        # Format for PostgreSQL vector
        if isinstance(query_embedding, list):
            query_vector = np.array(query_embedding, dtype=np.float32)
        else:
            query_vector = query_embedding

        if isinstance(query_vector, np.ndarray):
            pg_vector = f"[{','.join(map(str, query_vector.tolist()))}]"
        else:
            pg_vector = query_vector

        # Define base SQL for similarity search with cosine distance
        # Lower cosine distance means higher similarity
        sql = """
            SELECT
                ch.id,
                ch.document_id,
                1 - (ch.embedding <=> %s) as similarity
            FROM
                llm_document_chunk ch
            JOIN
                llm_document doc ON ch.document_id = doc.id
            WHERE
                ch.embedding IS NOT NULL
        """

        params = [pg_vector]

        # Add domain filters if needed
        if domain:
            if domain[0][0] == "document_id.id" and domain[0][1] == "in":
                sql += " AND doc.id IN %s"
                params.append(tuple(domain[0][2]))

        # Add similarity cutoff
        sql += " AND 1 - (ch.embedding <=> %s) >= %s"
        params.extend([pg_vector, self.similarity_cutoff])

        # Order by similarity and limit
        sql += " ORDER BY similarity DESC LIMIT %s"
        params.append(
            self.top_n * self.top_k
        )  # Get more results to ensure enough per document

        # Execute the search
        self.env.cr.execute(sql, params)
        results = self.env.cr.fetchall()

        # Process results
        chunk_ids = []
        result_lines = []
        processed_docs = set()
        doc_chunk_count = {}

        for chunk_id, doc_id, similarity in results:
            # Skip if we already have enough chunks for this document
            doc_chunk_count.setdefault(doc_id, 0)
            if doc_id in processed_docs and doc_chunk_count[doc_id] >= self.top_k:
                continue

            chunk_ids.append(chunk_id)
            doc_chunk_count[doc_id] = doc_chunk_count.get(doc_id, 0) + 1

            # Add to result lines with similarity score
            result_lines.append(
                (
                    0,
                    0,
                    {
                        "chunk_id": chunk_id,
                        "similarity": similarity,
                    },
                )
            )

            # Mark document as processed if we have enough chunks
            if doc_chunk_count[doc_id] >= self.top_k:
                processed_docs.add(doc_id)

            # Break if we have enough documents and chunks
            if len(processed_docs) >= self.top_n and all(
                count >= self.top_k for count in doc_chunk_count.values()
            ):
                break

        # Update wizard with results
        self.write(
            {
                "state": "results",
                "result_ids": [(6, 0, chunk_ids)],
                "result_lines": result_lines,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "llm.rag.search.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def action_back_to_search(self):
        """Go back to search form"""
        self.ensure_one()
        self.write(
            {
                "state": "search",
                "result_ids": [(5, 0, 0)],  # Clear results
                "result_lines": [(5, 0, 0)],  # Clear result lines
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "llm.rag.search.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }


class RAGSearchResultLine(models.TransientModel):
    _name = "llm.rag.search.result.line"
    _description = "RAG Search Result Line"
    _order = "similarity desc, id"

    wizard_id = fields.Many2one(
        "llm.rag.search.wizard",
        string="Wizard",
        required=True,
        ondelete="cascade",
    )

    chunk_id = fields.Many2one(
        "llm.document.chunk",
        string="Chunk",
        required=True,
        readonly=True,
    )

    document_id = fields.Many2one(
        related="chunk_id.document_id",
        string="Document",
        readonly=True,
        store=True,
    )

    document_name = fields.Char(
        related="document_id.name",
        string="Document Name",
        readonly=True,
    )

    chunk_name = fields.Char(
        related="chunk_id.name",
        string="Chunk Name",
        readonly=True,
    )

    content = fields.Text(
        related="chunk_id.content",
        string="Content",
        readonly=True,
    )

    similarity = fields.Float(
        string="Similarity",
        digits=(5, 4),
        readonly=True,
    )

    similarity_percentage = fields.Char(
        string="Similarity %",
        compute="_compute_similarity_percentage",
    )

    @api.depends("similarity")
    def _compute_similarity_percentage(self):
        for line in self:
            line.similarity_percentage = f"{line.similarity * 100:.2f}%"
