{
    "name": "Document Page External URL",
    "version": "16.0.1.0.0",
    "category": "Knowledge Management",
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "license": "AGPL-3",
    "summary": "Extend document pages with external URL support and LLM integration",
    "depends": [
        "document_page",
        "llm_knowledge",
    ],
    "data": [
        "views/document_page_views.xml",
    ],
    "external_dependencies": {
        "python": ["markdownify"],
    },
    "application": False,
    "installable": True,
}
