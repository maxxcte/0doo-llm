{
    "name": "LLM Thread",
    "summary": "Message thread support for LLM conversations",
    "description": """
        Extends the LLM integration module with conversation threading capabilities:
        - Persistent chat history
        - Real-time streaming responses
        - Message management
        - Thread organization
        - Chat export
    """,
    "category": "Technical",
    "version": "16.0.1.0.0",
    "depends": ["llm", "mail"],
    "external_dependencies": {},
    "data": [
        "security/llm_thread_security.xml",
        "security/ir.model.access.csv",
        "views/llm_model_views.xml",
        "views/llm_thread_views.xml",
    ],
    "assets": {
        "web.assets_backend": [
            # Components
            "llm_thread/static/src/components/llm_message/llm_message.js",
            "llm_thread/static/src/components/llm_message/llm_message.scss",
            "llm_thread/static/src/components/llm_message/llm_message.xml",
            "llm_thread/static/src/components/llm_message_list/llm_message_list.js",
            "llm_thread/static/src/components/llm_message_list/llm_message_list.scss",
            "llm_thread/static/src/components/llm_message_list/llm_message_list.xml",
            "llm_thread/static/src/components/llm_composer/llm_composer.js",
            "llm_thread/static/src/components/llm_composer/llm_composer.scss",
            "llm_thread/static/src/components/llm_composer/llm_composer.xml",
            "llm_thread/static/src/components/llm_thread_view/llm_thread_view.js",
            "llm_thread/static/src/components/llm_thread_view/llm_thread_view.scss",
            "llm_thread/static/src/components/llm_thread_view/llm_thread_view.xml",
            "llm_thread/static/src/components/llm_chat_dialog/llm_chat_dialog.js",
            "llm_thread/static/src/components/llm_chat_dialog/llm_chat_dialog.xml",
        ],
    },
    "license": "LGPL-3",
    "installable": True,
}
