{
    "name": "LLM PgVector",
    "summary": "Vector field and search capabilities using pgvector",
    "description": """
        Implements vector field and search capabilities for Odoo using pgvector.

        Features:
        - Vector field type with variable dimensions
        - Embedding mixin with similarity search
        - Vector index management
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "depends": ["base"],
    "external_dependencies": {
        "python": ["pgvector", "numpy"],
    },
    "pre_init_hook": "pre_init_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
