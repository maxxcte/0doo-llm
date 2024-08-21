{
    "name": "LLM PgVector",
    "summary": "Vector field and search capabilities using pgvector",
    "description": """
        Implements vector field and search capabilities for Odoo using pgvector.

        Features:
        - Vector field type with variable dimensions
        - Embedding storage and retrieval for chunks
        - Vector index management
        - Efficient vector search with pgvector
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "depends": ["llm", "llm_knowledge", "llm_store"],
    "external_dependencies": {
        "python": ["pgvector", "numpy"],
    },
    "data": {
        "views/llm_knowledge_chunk_embedding_views.xml"
    },
    "pre_init_hook": "pre_init_hook",
    "post_init_hook": "post_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
    "data": [
        "security/ir.model.access.csv",
    ],
}
