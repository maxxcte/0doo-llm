{
    "name": "LLM Prompt Templates",
    "summary": """
        Create and manage reusable prompt templates for LLM interactions""",
    "description": """
        This module extends the LLM integration base to support:
        - Creating reusable prompt templates
        - Dynamic arguments within prompts
        - Resource context inclusion
        - Multi-step prompt workflows
        - Prompt discovery and retrieval
    """,
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm"],
    "data": [
        "security/llm_prompt_security.xml",
        "security/ir.model.access.csv",
        "views/llm_prompt_views.xml",
        "views/llm_prompt_menu.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
