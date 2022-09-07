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
    "license": "LGPL-3",
    "installable": True,
}
