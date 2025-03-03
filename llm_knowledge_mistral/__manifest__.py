{
    "name": "LLM RAG Mistral",
    "summary": "Extend LLM RAG with Mistral document/image parsing capabilities",
    "description": """
        Extends the LLM RAG module with Mistral markdown-optimized parsing strategies.

        Features:
        - Integration with Mistral for resource parsing
        - Markdown-optimized parsing
        - Improved semantic parsing for better retrieval
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm_knowledge", "llm_mistral"],
    "author": "Mpve Solutions LLC",
    "website": "https://github.com/maxxcte",
    "data": [
        "views/llm_resource_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
