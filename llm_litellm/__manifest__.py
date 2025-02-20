{
    "name": "LiteLLM Proxy Integration",
    "summary": "LiteLLM proxy integration for LLM module",
    "description": """
        Implements LiteLLM proxy service for the LLM integration module.
        Supports proxying requests to various LLM providers through a central LiteLLM proxy server.

        Features:
        - Chat completions with streaming support
        - Text embeddings
        - Model listing
        - Rate limiting and cost tracking through proxy
    """,
    "category": "Technical",
    "version": "16.0.1.1.0",
    "depends": ["llm"],
    "external_dependencies": {
        "python": ["requests"],
    },
    "data": [
        "security/push_models_security.xml",
        "data/llm_publisher.xml",
        "views/provider_views.xml",
        "wizards/push_models_wizard_views.xml",
    ],
    "images": [
        "static/description/banner.jpeg",
    ],
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "license": "LGPL-3",
    "installable": True,
}
