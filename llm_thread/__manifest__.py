{
    "name": "Easy AI Chat",
    "summary": "Simple AI Chat for Odoo",
    "description": """
Easy AI Chat for Odoo
=====================
A user-friendly module that brings AI-powered chat to your Odoo environment. Integrate with multiple AI providers, manage real-time conversations, and enhance workflows with multimodal support.

Key Features:
- Multiple AI Providers: OpenAI, Anthropic, Grok, Ollama, DeepSeek, and more
- Real-Time Chat: Instant AI conversations integrated with Odoo's mail system
- Multimodal Support: Go beyond text with advanced AI models
- Full Odoo Integration: Link chats to any Odoo record for context
- Tool Integration: Enable AI to execute custom tools and functions
- Function Calling: Select specific tools for each thread to enhance AI capabilities

Getting Started:
1. Install this module and the "LLM Integration Base" dependency
2. Configure your AI provider API keys
3. Fetch available models with one click
4. Start chatting from anywhere in Odoo

Use cases include customer support automation, data analysis, training assistance, custom AI workflows, and automated tool execution for your business.

Contact: support@apexive.com
    """,
    "category": "Productivity, Discuss",
    "version": "16.0.1.1.1",
    "depends": ["base", "mail", "mail_message_stream", "web", "llm", "llm_tool", "llm_mail_message_subtypes"],
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "external_dependencies": {"python": ["emoji"]},
    "data": [
        "security/llm_thread_security.xml",
        "security/ir.model.access.csv",
        "views/llm_thread_views.xml",
        "views/menu.xml",
    ],
    "assets": {
        "web.assets_backend": [
            "llm_thread/static/lib/marked/marked.min.js",
            "llm_thread/static/src/utils/markdown_utils.js",
            # Models
            "llm_thread/static/src/models/main.js",
            "llm_thread/static/src/models/messaging.js",
            "llm_thread/static/src/models/llm_chat.js",
            "llm_thread/static/src/models/llm_chat_view.js",
            "llm_thread/static/src/models/thread.js",
            "llm_thread/static/src/models/composer.js",
            "llm_thread/static/src/models/composer_view.js",
            "llm_thread/static/src/models/llm_model.js",
            "llm_thread/static/src/models/llm_provider.js",
            "llm_thread/static/src/models/thread_view.js",
            "llm_thread/static/src/models/llm_chat_thread_header_view.js",
            "llm_thread/static/src/models/chatter.js",
            "llm_thread/static/src/models/llm_tool.js",
            "llm_thread/static/src/models/llm_tool_message.js",
            "llm_thread/static/src/models/message.js",
            "llm_thread/static/src/models/message_action.js",
            "llm_thread/static/src/models/message_action_list.js",
            "llm_thread/static/src/models/message_action_view.js",
            # Components
            "llm_thread/static/src/components/llm_chat/llm_chat.js",
            "llm_thread/static/src/components/llm_chat/llm_chat.xml",
            "llm_thread/static/src/components/llm_chat_thread_list/llm_chat_thread_list.js",
            "llm_thread/static/src/components/llm_chat_thread_list/llm_chat_thread_list.xml",
            "llm_thread/static/src/components/llm_chat_thread/llm_chat_thread.js",
            "llm_thread/static/src/components/llm_chat_thread/llm_chat_thread.scss",
            "llm_thread/static/src/components/llm_chat_thread/llm_chat_thread.xml",
            "llm_thread/static/src/components/llm_chat_container/llm_chat_container.js",
            "llm_thread/static/src/components/llm_chat_container/llm_chat_container.xml",
            "llm_thread/static/src/components/llm_chat_container/llm_chat_container.scss",
            "llm_thread/static/src/components/llm_chat_sidebar/llm_chat_sidebar.js",
            "llm_thread/static/src/components/llm_chat_sidebar/llm_chat_sidebar.xml",
            "llm_thread/static/src/components/llm_chat_sidebar/llm_chat_sidebar.scss",
            "llm_thread/static/src/components/llm_chat_composer/llm_chat_composer.js",
            "llm_thread/static/src/components/llm_chat_composer/llm_chat_composer.xml",
            "llm_thread/static/src/components/llm_chat_composer/llm_chat_composer.scss",
            "llm_thread/static/src/components/llm_chat_composer_text_input/llm_chat_composer_text_input.js",
            "llm_thread/static/src/components/llm_chat_composer_text_input/llm_chat_composer_text_input.xml",
            "llm_thread/static/src/components/llm_chat_composer_text_input/llm_chat_composer_text_input.scss",
            "llm_thread/static/src/components/llm_chat_message_list/llm_chat_message_list.js",
            "llm_thread/static/src/components/llm_chat_message_list/llm_chat_message_list.xml",
            "llm_thread/static/src/components/llm_chat_thread_header/llm_chat_thread_header.js",
            "llm_thread/static/src/components/llm_chat_thread_header/llm_chat_thread_header.xml",
            "llm_thread/static/src/components/llm_chat_thread_header/llm_chat_thread_header.scss",
            "llm_thread/static/src/components/llm_chatter_topbar/llm_chatter_topbar.xml",
            "llm_thread/static/src/components/llm_chatter_topbar/llm_chat_topbar.scss",
            "llm_thread/static/src/components/llm_chatter/llm_chatter.xml",
            "llm_thread/static/src/components/message/message.xml",
            "llm_thread/static/src/components/message/message.scss",
            # Client Actions
            "llm_thread/static/src/llm_chat_client_action.js",
            # Styles
            (
                "after",
                "web/static/src/scss/pre_variables.scss",
                "llm_thread/static/src/components/llm_chat/llm_chat.scss",
            ),
            (
                "after",
                "web/static/src/scss/pre_variables.scss",
                "llm_thread/static/src/components/llm_chat_thread_list/llm_chat_thread_list.scss",
            ),
        ],
    },
    "images": [
        "static/description/banner.jpeg",
    ],
    "license": "LGPL-3",
    "installable": True,
    "application": True,
    "auto_install": False,
}
