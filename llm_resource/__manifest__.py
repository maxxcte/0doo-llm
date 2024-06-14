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
        "views/llm_resource_views.xml",
        "wizards/create_resource_wizard_views.xml",
        "wizards/upload_resource_wizard_views.xml",
        "data/server_actions.xml",
        "views/menu.xml",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
