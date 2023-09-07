{
    "name": "LLM Agent",
    "summary": """
        LLM/AI Agent module for Odoo
    """,
    "description": """
Agentic AI (LLM) Agent for Odoo
==================
Configure AI agents with specific roles, goals, and tools to enhance your AI interactions.

Key Features:
- Create and configure AI agents with specific roles and goals
- Assign preferred tools to each agent
- Automatically generate system prompts based on agent configuration
- Attach agents to chat threads for consistent behavior
- Full integration with the LLM chat system

Use cases include creating specialized agents for customer support, data analysis, training assistance, and more.
    """,
    "category": "Productivity, Discuss",
    "version": "16.0.1.0.0",
    "depends": ["base", "mail", "web", "llm", "llm_thread", "llm_tool"],
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "data": [
        "security/ir.model.access.csv",
        "views/llm_agent_views.xml",
        "views/llm_thread_views.xml",
        "views/llm_menu_views.xml",
    ],
    "images": [
        "static/description/banner.jpeg",
    ],
    "assets": {
        "web.assets_backend": [
            "llm_agent/static/src/models/main.js",
            # Models
            "llm_agent/static/src/models/llm_agent.js",
            "llm_agent/static/src/models/llm_chat.js",
            "llm_agent/static/src/models/thread.js",
            "llm_agent/static/src/models/llm_chat_thread_header_view.js",
            # Components
            "llm_agent/static/src/components/llm_chat_thread_header/llm_chat_thread_header.js",
            "llm_agent/static/src/components/llm_chat_thread_header/llm_chat_thread_header.xml",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": False,
    "auto_install": False,
}
