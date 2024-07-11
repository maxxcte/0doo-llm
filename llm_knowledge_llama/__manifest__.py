{
    "name": "LLM RAG LlamaIndex",
    "summary": "Extend LLM RAG with LlamaIndex markdown chunking capabilities",
    "description": """
        Extends the LLM RAG module with LlamaIndex markdown-optimized chunking strategies.

        Features:
        - Integration with LlamaIndex for resource chunking
        - Markdown-optimized node parsing
        - Improved semantic chunking for better retrieval
        - Support for LlamaIndex's advanced chunking strategies
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm_knowledge"],
    "external_dependencies": {
        "python": ["llama_index", "nltk"],
    },
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "data": [],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
