{
    "name": "Ollama LLM Integration",
    "summary": "Ollama provider integration for LLM module",
    "description": """
        Implements Ollama provider service for the LLM integration module.
        Supports local deployment of various open source models.
    """,
    "author": "Mpve Solutions LLC",
    "website": "https://github.com/maxxcte",
    "category": "Technical",
    "version": "16.0.1.1.0",
    "depends": ["llm", "llm_tool", "llm_mail_message_subtypes"],
    "external_dependencies": {
        "python": ["ollama"],
    },
    "data": [
        "data/llm_publisher.xml",
    ],
    "images": [
        "static/description/banner.jpeg",
    ],
    "license": "LGPL-3",
    "installable": True,
}
