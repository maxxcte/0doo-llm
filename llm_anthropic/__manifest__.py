{
    "name": "Anthropic LLM Integration",
    "summary": "Anthropic provider integration for LLM module",
    "description": """
        Implements Anthropic provider service for the LLM integration module.
        Supports Claude models for chat and multimodal capabilities.
    """,
    "category": "Technical",
    "version": "16.0.1.1.0",
    "depends": ["llm"],
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "external_dependencies": {
        "python": ["anthropic"],
    },
    "data": [
        "data/llm_publisher.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
}
