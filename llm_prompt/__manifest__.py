{
    "name": "LLM Prompt Templates",
    "summary": """
        Create and manage reusable prompt templates for LLM interactions""",
    "description": """
        This module extends the LLM integration base to support:
        - Creating reusable prompt templates
        - Dynamic arguments within prompts
        - Multi-step prompt workflows
        - Prompt discovery and retrieval
        - Categories and tags for organization
    """,
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm"],
    "data": [
        "security/ir.model.access.csv",
        "data/llm_prompt_tag_data.xml",
        "data/llm_prompt_category_data.xml",
        "views/llm_prompt_views.xml",
        "views/llm_prompt_template_views.xml",
        "views/llm_prompt_tag_views.xml",
        "views/llm_prompt_category_views.xml",
        "views/menu.xml",
        "wizards/llm_prompt_test_views.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
