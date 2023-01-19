{
    "name": "Ollama LLM Integration",
    "summary": "Ollama provider integration for LLM module",
    "description": """
        Implements Ollama provider service for the LLM integration module.
        Supports local deployment of various open source models.
    """,
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm"],
    "external_dependencies": {
        "python": ["ollama"],
    },
    "data": [
        "data/llm_publisher.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
}
