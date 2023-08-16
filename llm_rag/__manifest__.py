{
    "name": "LLM RAG",
    "summary": "Retrieval Augmented Generation for LLM with Vector Search",
    "description": """
        Implements Retrieval Augmented Generation for the LLM module.

        Features:
        - Document management for RAG
        - Document processing pipeline (retrieve, parse, chunk, embed)
        - Integration with LLM models
        - Vector search using pgvector
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm", "llm_pgvector"],
    "external_dependencies": {
        "python": ["PyMuPDF", "numpy"],
    },
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "data": [
        "security/ir.model.access.csv",
        "views/llm_document_views.xml",
        "views/llm_document_collection_views.xml",
        "views/llm_document_chunk_views.xml",
        "wizards/rag_search_wizard_views.xml",
        "wizards/create_rag_document_wizard_views.xml",
        "wizards/add_domain_wizard_views.xml",
        "data/server_actions.xml",
        "views/menu.xml",
    ],
    "assets": {},
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
