{
    "name": "LLM Chroma",
    "summary": "Vector store integration with Chroma for LLM features",
    "description": """
        Implements vector storage and search capabilities for Odoo using Chroma vector database.

        Features:
        - Chroma integration for vector storage
        - HTTP client connection to Chroma server
        - Collection management for vector collections
        - Vector search with similarity functions
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "author": "Mpve Solutions LLC",
    "website": "https://github.com/maxxcte",
    "depends": ["llm", "llm_knowledge", "llm_store"],
    "external_dependencies": {
        "python": ["chromadb-client", "numpy"],
    },
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
}
