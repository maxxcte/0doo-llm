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
    "depends": ["llm", "llm_pgvector", "llm_resource"],
    "external_dependencies": {
        "python": ["PyMuPDF", "numpy"],
    },
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "data": [
        "security/ir.model.access.csv",
        "views/llm_knowledge_collection_views.xml",
        "views/llm_knowledge_chunk_views.xml",
        "views/menu.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
