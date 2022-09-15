{
    "name": "LLM Thread",
    "summary": "LLM Chat Threads",
    "description": """
LLM Chat Threads for Odoo
========================
This module adds support for LLM chat threads.
    """,
    "category": "Productivity",
    "version": "16.0.1.0.0",
    "depends": ["base", "mail", "web", "llm"],
    "external_dependencies": {},
    "data": [
        "security/llm_thread_security.xml",
        "security/ir.model.access.csv",
        "views/llm_thread_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Models
            'llm_thread/static/src/models/main.js',
            'llm_thread/static/src/models/messaging.js',
            'llm_thread/static/src/models/llm_chat.js',
            'llm_thread/static/src/models/llm_chat_view.js',
            'llm_thread/static/src/models/thread.js',
            
            # Components
            'llm_thread/static/src/components/llm_chat/llm_chat.js',
            'llm_thread/static/src/components/llm_chat/llm_chat.xml',
            'llm_thread/static/src/components/llm_chat_thread_list/llm_chat_thread_list.js',
            'llm_thread/static/src/components/llm_chat_thread_list/llm_chat_thread_list.xml',
            'llm_thread/static/src/components/llm_chat_thread/llm_chat_thread.js',
            'llm_thread/static/src/components/llm_chat_thread/llm_chat_thread.xml',
            'llm_thread/static/src/components/llm_chat_container/llm_chat_container.js',
            'llm_thread/static/src/components/llm_chat_container/llm_chat_container.xml',
            'llm_thread/static/src/components/llm_chat_container/llm_chat_container.scss',
            'llm_thread/static/src/components/llm_chat_sidebar/llm_chat_sidebar.js',
            'llm_thread/static/src/components/llm_chat_sidebar/llm_chat_sidebar.xml',
            'llm_thread/static/src/components/llm_chat_sidebar/llm_chat_sidebar.scss',
            # Client Actions
            'llm_thread/static/src/llm_chat_client_action.js',
            
            # Styles
            ('after', 'web/static/src/scss/pre_variables.scss', 'llm_thread/static/src/components/llm_chat/llm_chat.scss'),
            ('after', 'web/static/src/scss/pre_variables.scss', 'llm_thread/static/src/components/llm_chat_thread_list/llm_chat_thread_list.scss'),
        ],
    },
    "license": "LGPL-3",
    "installable": True,
    "application": True,
    "auto_install": False,
}
