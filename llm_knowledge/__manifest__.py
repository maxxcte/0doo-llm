{
    "name": "LLM Knowledge",
    "summary": "Retrieval Augmented Generation for LLM with Vector Search",
    "description": """
        Implements Retrieval Augmented Generation (chunking and embedding) for the LLM module.

        Features:
        - Document collections for RAG
        - Document chunking pipeline
        - Document embedding integration
        - Vector search using pgvector
        - PDF processing and text extraction
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm", "llm_resource", "llm_store"],
    "external_dependencies": {
        "python": ["PyMuPDF", "numpy"],
    },
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "data": [
        # Security must come first
        "security/ir.model.access.csv",
        # Views for models
        "views/llm_resource_views.xml",  # Defines views for llm.resource
        "views/llm_knowledge_collection_views.xml",
        "views/llm_knowledge_chunk_views.xml",
        # Wizard Views
        "wizards/create_rag_resource_wizard_views.xml",
        "wizards/upload_resource_wizard_views.xml",
        # Data / Actions
        "data/server_actions.xml",
        # Menus must come last
        "views/menu.xml",
    ],
    "images": [
        "static/description/banner.jpeg",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
