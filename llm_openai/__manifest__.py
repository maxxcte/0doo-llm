{
    "name": "OpenAI LLM Integration",
    "summary": "OpenAI provider integration for LLM module",
    "description": """
        Implements OpenAI provider service for the LLM integration module.
        Supports GPT models for chat and embedding capabilities.
    """,
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "category": "Technical",
    "version": "16.0.1.1.1",
    "depends": ["llm", "llm_tool"],
    "external_dependencies": {
        "python": ["openai"],
    },
    "data": [
        "data/llm_publisher.xml",
        "data/llm_provider.xml",
        "data/llm_model.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
}
