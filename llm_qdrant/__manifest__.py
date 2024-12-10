{
    "name": "LLM Qdrant Integration",
    "version": "16.0.1.0.0",
    "category": "Technical",
    "summary": "Integrates Qdrant vector store with the Odoo LLM framework.",
    "description": """
Provides an llm.store implementation using the Qdrant vector database.
Requires the qdrant-client Python package.
    """,
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "depends": ["llm_knowledge", "llm_store"],
    "installable": True,
    "application": False,
    "auto_install": False,
    "external_dependencies": {
        "python": ["qdrant-client"],
    },
    "license": "LGPL-3",
}
