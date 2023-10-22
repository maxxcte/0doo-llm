{
    "name": "LLM Knowledge Automation",
    "summary": "Automates RAG document creation and synchronization with collections",
    "description": """
        Extends the LLM Knowledge module to automatically keep collections synchronized
        with updated records through automated actions.

        Features:
        - Automatically create/update RAG documents when records change
        - Synchronize collections with their domain filters via automated actions
        - Remove documents from collections when they no longer match filters
        - Trigger document processing pipeline automatically
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm_knowledge", "base_automation"],
    "external_dependencies": {
        "python": [],
    },
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "data": [
        "views/llm_document_collection_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
