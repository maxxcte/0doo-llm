{
    "name": "Replicate LLM Integration",
    "summary": "Replicate provider integration for LLM module",
    "description": """
        Implements Replicate provider service for the LLM integration module.
        Supports diverse AI models and custom model deployments.
    """,
    "category": "Technical",
    "version": "16.0.1.1.0",
    "depends": ["llm"],
    "external_dependencies": {
        "python": ["replicate"],
    },
    "data": [
        "data/llm_publisher.xml",
    ],
    "images": [
        "static/description/banner.jpeg",
    ],
    "website": "https://github.com/apexive/odoo-llm",
    "author": "Apexive Solutions LLC",
    "license": "LGPL-3",
    "installable": True,
}
