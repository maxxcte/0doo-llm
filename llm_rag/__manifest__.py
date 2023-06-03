{
    "name": "LLM RAG",
    "summary": "Retrieval Augmented Generation for LLM",
    "description": """
        Implements Retrieval Augmented Generation for the LLM module.

        Features:
        - Document management for RAG
        - Document processing pipeline (retrieve, parse, chunk, embed)
        - Integration with LLM models
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm"],
    "external_dependencies": {
        "python": ["PyMuPDF"],
    },
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "data": [
        "security/ir.model.access.csv",
        "views/llm_document_views.xml",
        "views/menu.xml",
        "wizards/create_rag_document_wizard_views.xml",
        "data/server_actions.xml",
    ],
    "assets": {},
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
