{
    "name": "LLM Agent",
    "version": "16.0.1.0.0",
    "category": "AI",
    "summary": "Tools for LLM models to interact with Odoo",
    "author": "Odoo",
    "website": "https://www.odoo.com",
    "license": "LGPL-3",
    "depends": ["base", "mail", "llm"],
    "data": [
        "security/ir.model.access.csv",
        "data/llm_tool_data.xml",
    ],
    "auto_install": False,
    "application": False,
    "installable": True,
}