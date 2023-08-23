# Copyright 2025 Apexive Solutions LLC
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

{
    "name": "Document Page External URL",
    "version": "16.0.1.0.0",
    "category": "Knowledge Management",
    "author": "Apexive Solutions LLC",
    "website": "https://github.com/apexive/odoo-llm",
    "license": "AGPL-3",
    "depends": ["document_page"],
    "data": [
        "views/document_page_view.xml",
    ],
    "demo": [],
    "external_dependencies": {
        "python": ["requests"],
    },
    "installable": True,
    "auto_install": False,
    "summary": "Adds the ability to link and retrieve external content for document pages",
    "description": """
Document Page External URL
==========================

This module extends document_page to add:

* External URL field to document pages
* Ability to retrieve content from the external URL
* History tracking of content retrieved from external URLs
    """,
}
