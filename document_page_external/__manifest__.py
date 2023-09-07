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
        "security/ir.model.access.csv",
        "views/document_page_view.xml",
        "views/document_page_link.xml",
        "data/scheduled_actions.xml",  # New scheduled action
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
* Automatic extraction and tracking of links from page content
* "Links" tab to view and manage links associated with a page
* Automatic detection of MIME types and file sizes using HEAD requests
* Background processing of MIME type detection for better performance
    """,
}