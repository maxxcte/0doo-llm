{
    "name": "LLM Agent",
    "version": "16.0.1.0.0",
    "category": "AI",
    "summary": "Tools for LLM models to interact with Odoo",
    "author": "Odoo",
    "website": "https://www.odoo.com",
    "license": "LGPL-3",
    "depends": ["base", "mail", "llm", "llm_thread", "llm_openai"],
    "data": [
        "security/ir.model.access.csv",
        "views/llm_thread_views.xml",
        "views/llm_tool_views.xml",
    ],
    "auto_install": False,
    "application": False,
    "installable": True,
}