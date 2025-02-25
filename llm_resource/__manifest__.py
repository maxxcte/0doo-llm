{
    "name": "LLM Resource",
    "summary": "Base document resource management for LLM modules",
    "description": """
        Provides the base document resource functionality for LLM modules.

        Features:
        - Base document resource model
        - Resource retrieval interfaces
        - Resource parsing interfaces
        - HTTP retrieval for external URLs
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm"],
    "external_dependencies": {
        "python": ["requests", "markdownify"],
    },
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "data": [
        "security/ir.model.access.csv",
        "data/server_actions.xml",
        "views/llm_resource_views.xml",
        "views/menu.xml",
    ],
    "images": [
        "static/description/banner.jpeg",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
