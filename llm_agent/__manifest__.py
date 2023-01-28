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
        "views/llm_tool_server_action_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "llm_agent/static/src/models/llm_chat.js",
            "llm_agent/static/src/models/llm_thread.js",
            "llm_agent/static/src/models/llm_tool.js",
            "llm_agent/static/src/components/llm_chat_thread_header/llm_chat_thread_header_patch.js",
            "llm_agent/static/src/components/llm_chat_thread_header/llm_chat_thread_header.xml",
        ],
    },
    "auto_install": False,
    "application": False,
    "installable": True,
}