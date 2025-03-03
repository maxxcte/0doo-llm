{
    "name": "LLM Knowledge Automation",
    "summary": "Automates RAG resource creation and synchronization with collections",
    "description": """
        Extends the LLM Knowledge module to automatically keep collections synchronized
        with updated records through automated actions.

        Features:
        - Automatically create/update RAG resources when records change
        - Synchronize collections with their domain filters via automated actions
        - Remove resources from collections when they no longer match filters
        - Trigger resource processing pipeline automatically
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm_knowledge", "base_automation"],
    "external_dependencies": {
        "python": [],
    },
    "author": "Mpve Solutions LLC",
    "website": "https://github.com/maxxcte",
    "data": [
        "views/llm_knowledge_collection_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
    "images": [
        "static/description/banner.jpeg",
    ],
}
