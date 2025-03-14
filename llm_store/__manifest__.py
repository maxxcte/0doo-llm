{
    "name": "LLM Vector Store Base",
    "summary": """
        Integration with various vector database providers for LLM applications""",
    "description": """
        Provides integration with vector stores for:
        - Vector storage and retrieval
        - Similarity search
        - Collection management
        - RAG (Retrieval Augmented Generation) support

    """,
    "author": "Mpve Solutions LLC",
    "website": "https://github.com/maxxcte",
    "category": "Technical",
    "version": "16.0.1.0",
    "depends": ["llm", "benchmark"],
    "data": [
        "security/ir.model.access.csv",
        "views/llm_store_views.xml",
        "views/llm_store_menu_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
}
