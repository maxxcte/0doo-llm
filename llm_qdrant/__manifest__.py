{
    'name': 'LLM Qdrant Integration',
    'version': '1.0',
    'category': 'AI/LLM',
    'summary': 'Integrates Qdrant vector store with the Odoo LLM framework.',
    'description': """
Provides an llm.store implementation using the Qdrant vector database.
Requires the qdrant-client Python package.
    """,
    'author': 'Apexive',
    'website': 'https://apexive.com',
    'depends': ['llm_store'],
    'data': [
        # Add security rules if needed
        # Add views if needed
    ],
    'installable': True,
    'application': False,
    'auto_install': False,
    'external_dependencies': {
        'python': ['qdrant-client'],
    },
    'license': 'LGPL-3',
}
