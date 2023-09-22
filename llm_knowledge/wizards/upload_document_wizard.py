import base64
import logging
import re
from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class UploadDocumentWizard(models.TransientModel):
    _name = "llm.upload.document.wizard"
    _description = "Upload RAG Documents Wizard"

    collection_id = fields.Many2one(
        "llm.document.collection",
        string="Collection",
        required=True,
        help="Collection to which documents will be added",
    )
    file_ids = fields.Many2many(
        'ir.attachment',
        string='Files',
        help="Local files to upload"
    )
    external_urls = fields.Text(
        string="External URLs",
        help="External URLs to include, one per line"
    )
    document_name_template = fields.Char(
        string="Document Name Template",
        default="{filename}",
        help="Template for document names. Use {filename}, {collection}, and {index} as placeholders.",
        required=True,
    )
    process_immediately = fields.Boolean(
        string="Process Immediately",
        default=False,
        help="If checked, documents will be immediately processed through the RAG pipeline",
    )
    state = fields.Selection(
        [
            ("confirm", "Confirm"),
            ("done", "Done"),
        ],
        default="confirm",
    )
    created_document_ids = fields.Many2many(
        "llm.document",
        string="Created Documents",
    )
    created_count = fields.Integer(string="Created", compute="_compute_created_count")

    @api.depends("created_document_ids")
    def _compute_created_count(self):
        for wizard in self:
            wizard.created_count = len(wizard.created_document_ids)

    def _extract_filename_from_url(self, url):
        """Extract a clean filename from a URL"""
        # Try to extract filename from the URL path
        match = re.search(r'/([^/]+)(?:\?.*)?$', url)
        if match:
            filename = match.group(1)
            # Remove query string if present
            if '?' in filename:
                filename = filename.split('?')[0]
            return filename
        return url

    def action_upload_documents(self):
        """Create RAG documents from uploaded files and external URLs"""
        self.ensure_one()
        collection = self.collection_id
        created_documents = self.env["llm.document"]

        # Validate that at least one file or URL is provided
        if not self.file_ids and not self.external_urls:
            raise UserError(_("Please provide at least one file or URL"))

        # Process local files
        for index, attachment in enumerate(self.file_ids):
            document_name = self.document_name_template.format(
                filename=attachment.name,
                collection=collection.name,
                index=index + 1,
            )

            # Create RAG document
            document = self.env["llm.document"].create({
                "name": document_name,
                "res_model": "ir.attachment",
                "res_id": attachment.id,
                "collection_ids": [(4, collection.id)],
            })

            # Process document if requested
            if self.process_immediately:
                document.process_document()

            created_documents |= document

        # Process external URLs
        if self.external_urls:
            urls = [url.strip() for url in self.external_urls.split('\n') if url.strip()]
            for index, url in enumerate(urls):
                # Extract filename from URL for naming
                filename = self._extract_filename_from_url(url)

                document_name = self.document_name_template.format(
                    filename=filename,
                    collection=collection.name,
                    index=len(self.file_ids) + index + 1,
                )

                # Create attachment for URL
                attachment = self.env['ir.attachment'].create({
                    'name': filename,
                    'type': 'url',
                    'url': url,
                    'res_model': 'llm.document.collection',
                    'res_id': collection.id,
                })

                # Create RAG document
                document = self.env["llm.document"].create({
                    "name": document_name,
                    "res_model": "ir.attachment",
                    "res_id": attachment.id,
                    "collection_ids": [(4, collection.id)],
                })

                # Process document if requested
                if self.process_immediately:
                    document.process_document()

                created_documents |= document

        # Update wizard state
        self.write({
            "state": "done",
            "created_document_ids": [(6, 0, created_documents.ids)],
        })

        return {
            "type": "ir.actions.act_window",
            "res_model": "llm.upload.document.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def action_view_documents(self):
        """Open the created documents"""
        return {
            "name": "Uploaded RAG Documents",
            "type": "ir.actions.act_window",
            "res_model": "llm.document",
            "view_mode": "tree,form,kanban",
            "domain": [("id", "in", self.created_document_ids.ids)],
        }