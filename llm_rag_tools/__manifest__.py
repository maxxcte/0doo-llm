{
    'name': 'LLM RAG Tools',
    'version': '1.0',
    'category': 'Productivity/Tools',
    'author': 'Apexive Solutions LLC',
    'website': 'https://github.com/apexive/odoo-llm',
    'summary': 'Tools for LLMs to interact with RAG functionality',
    'description': """
LLM RAG Tools
=============
This module provides tools for Large Language Models to interact with 
Retrieval-Augmented Generation (RAG) functionality.

Features:
- Document retriever tool for semantic search
- Integration with LLM tools framework
    """,
    'depends': ['llm_rag', 'llm_tool'],
    'data': [
        'security/ir.model.access.csv',
        'data/llm_tool_data.xml',
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'LGPL-3',
}
