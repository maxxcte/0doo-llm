{
    "name": "LLM Tool RAG",
    "version": "16.0.1.0.0",
    "category": "Productivity/Tools",
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "summary": "Tools for LLMs to interact with RAG functionality",
    "description": """
LLM Tool RAG
=============
This module provides tools for Large Language Models to interact with
Retrieval-Augmented Generation (RAG) functionality.

Features:
- Document retriever tool for semantic search
- Integration with LLM tools framework
- Reusable document search functionality
- Semantic and hybrid search capabilities
    """,
    "depends": ["llm_knowledge", "llm_tool"],
    "data": [
        "data/llm_tool_data.xml",
    ],
    "images": [
        "static/description/banner.jpeg",
    ],
    "installable": True,
    "application": False,
    "auto_install": False,
    "license": "LGPL-3",
    "maintainer": "Apexive Solutions LLC",
}
