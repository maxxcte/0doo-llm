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
        "views/llm_thread_views.xml",
        
    ],
    "assets": {
        "web.assets_backend": [
            # Models
            'llm_thread/static/src/models/llm_chat.js',
            'llm_thread/static/src/models/llm_chat_view.js',
            'llm_thread/static/src/models/messaging.js',
            'llm_thread/static/src/models/thread.js',
            'llm_thread/static/src/models/main.js',
            
            # Components
            'llm_thread/static/src/components/llm_chat_thread_list/llm_chat_thread_list.js',
            'llm_thread/static/src/components/llm_chat_thread_list/llm_chat_thread_list.xml',
            
            # Styles
            ('after', 'web/static/src/scss/pre_variables.scss', 'llm_thread/static/src/components/llm_chat_thread_list/llm_chat_thread_list.scss'),
        ],
    },
    "license": "LGPL-3",
    "installable": True,
}
