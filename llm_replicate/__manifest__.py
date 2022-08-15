{
    "name": "Replicate LLM Integration",
    "summary": "Replicate provider integration for LLM module",
    "description": """
        Implements Replicate provider service for the LLM integration module.
        Supports diverse AI models and custom model deployments.
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm"],
    "external_dependencies": {
        "python": ["replicate"],
    },
    "data": [
        "data/llm_publisher.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
}
