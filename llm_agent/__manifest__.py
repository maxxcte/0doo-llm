{
    "name": "LLM Agent",
    "version": "16.0.1.0.0",
    "category": "AI",
    "summary": "Advanced tools for LLM models to interact with Odoo, including customizable schemas and descriptions",
    "description": """
        Automate Your Odoo Database with AI Agents & Chat AI | ChatGPT, Grok, Anthropic, DeepSeek

        Boost your Odoo database automation with AI-powered agents using ChatGPT, Grok, Anthropic, and DeepSeek. Streamline 
        workflows, optimize data management, and enhance productivity with AI tools seamlessly integrated into your Odoo 
        instance. This module provides a robust framework for integrating Large Language Models (LLMs) with Odoo, enabling 
        intelligent interactions through configurable tools. Key features include:

        - Definition and management of LLM tools with custom implementations
        - Support for dynamic schema generation from Pydantic models
        - Flexible override options for tool descriptions and schemas
        - Integration with Odoo mail threads for chat-like interactions with AI assistants
        - Extensible architecture for adding new tool implementations

        Perfect for businesses looking to leverage AI-driven ERP management, this module empowers administrators to create, 
        configure, and customize LLM tools, supporting intelligent Odoo agents that automate workflows and enhance business 
        automation.
    """,
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "license": "LGPL-3",
    "depends": ["base", "mail", "llm", "llm_thread", "llm_openai"],
    "data": [
        "security/ir.model.access.csv",
        "views/menu_views.xml",
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