{
    "name": "LLM MCP",
    "version": "16.0.1.0.0",
    "category": "Technical",
    "summary": "Model Context Protocol (MCP) integration for LLM models",
    "description": """
        Model Context Protocol (MCP) Integration for Odoo LLM

        This module extends LLM integration in Odoo by adding support for the Model Context Protocol (MCP),
        allowing connection to external MCP-compliant servers that provide tool implementations. Key features include:

        - Connect to external MCP servers via standard I/O communication
        - Auto-discover and register tools exposed by MCP servers
        - Execute MCP tools through LLM conversations
        - Support for the JSON-RPC 2.0 based Model Context Protocol standard
        - Simple management interface for MCP server connections
    """,
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "license": "LGPL-3",
    "depends": ["base", "mail", "llm", "llm_tool"],
    "external_dependencies": {
        "python": [],
    },
    "data": [
        "security/ir.model.access.csv",
        "views/llm_mcp_server_views.xml",
        "views/llm_menu_views.xml",
    ],
    "images": [
        "static/description/banner.jpeg",
    ],
    "auto_install": False,
    "application": False,
    "installable": True,
}
