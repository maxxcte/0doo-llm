import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UploadResourceWizard(models.TransientModel):
    _name = "llm.upload.resource.wizard" # Keep original name or rename if preferred
    _description = "Upload RAG Resources Wizard"

    collection_id = fields.Many2one(
        "llm.knowledge.collection", # Target llm.knowledge.collection
        string="Collection",
        required=True, # Collection is required here
        help="Collection to which resources will be added",
    )
    file_ids = fields.Many2many(
        "ir.attachment", string="Files", help="Local files to upload"
    )
    external_urls = fields.Text(
        string="External URLs", help="External URLs to include, one per line"
    )
    # Field renamed for clarity
    resource_name_template = fields.Char(
        string="Resource Name Template",
        default="{filename}",
        help="Template for resource names. Use {filename}, {collection}, and {index} as placeholders.",
        required=True,
    )
    process_immediately = fields.Boolean(
        string="Process Immediately",
        default=False,
        help="If checked, resources will be immediately processed through the RAG pipeline",
    )
    state = fields.Selection(
        [
            ("confirm", "Confirm"),
            ("done", "Done"),
        ],
        default="confirm",
    )
    # Field renamed and target model changed
    created_resource_ids = fields.Many2many(
        "llm.resource", # Target llm.resource
        string="Created Resources",
    )
    created_count = fields.Integer(string="Created", compute="_compute_created_count")

    @api.depends("created_resource_ids")
    def _compute_created_count(self):
        for wizard in self:
            wizard.created_count = len(wizard.created_resource_ids)

    def _extract_filename_from_url(self, url):
        """Extract a clean filename from a URL"""
        # This utility method remains the same
        match = re.search(r"/([^/]+)(?:\?.*)?$", url)
        if match:
            filename = match.group(1)
            # Remove query string if present
            if "?" in filename:
                filename = filename.split("?")[0]
            return filename
        return url

    # Method renamed for clarity
    def action_upload_resources(self):
        """Create RAG resources from uploaded files and external URLs"""
        self.ensure_one()
        collection = self.collection_id
        created_resources = self.env["llm.resource"] # Target llm.resource

        # Get the ir.model record for ir.attachment
        # Renamed variable
        attachment_model_id_rec = (
            self.env["ir.model"].search([("model", "=", "ir.attachment")], limit=1)
        )
        if not attachment_model_id_rec:
            raise UserError(_("Could not find ir.attachment model"))
        attachment_model_id = attachment_model_id_rec.id

        # Validate that at least one file or URL is provided
        if not self.file_ids and not self.external_urls:
            raise UserError(_("Please provide at least one file or URL"))

        # Process local files
        for index, attachment in enumerate(self.file_ids):
            # Use renamed field
            resource_name = self.resource_name_template.format(
                filename=attachment.name,
                collection=collection.name, # Use collection name
                index=index + 1,
            )

            # Create RAG resource using model_id
            resource = self.env["llm.resource"].create( # Target llm.resource
                {
                    "name": resource_name,
                    "model_id": attachment_model_id,
                    "res_id": attachment.id,
                    "collection_ids": [(4, collection.id)], # Link to collection
                }
            )

            # Process resource if requested (full RAG pipeline)
            if self.process_immediately:
                resource.process_resource() # Calls overridden method

            created_resources |= resource

        # Process external URLs
        if self.external_urls:
            urls = [
                url.strip() for url in self.external_urls.split("\n") if url.strip()
            ]
            for index, url in enumerate(urls):
                # Extract filename from URL for naming
                filename = self._extract_filename_from_url(url)

                # Use renamed field
                resource_name = self.resource_name_template.format(
                    filename=filename,
                    collection=collection.name, # Use collection name
                    index=len(self.file_ids) + index + 1,
                )

                # Create attachment for URL
                attachment = self.env["ir.attachment"].create(
                    {
                        "name": filename,
                        "type": "url",
                        "url": url,
                        # Don't link attachment directly to collection, link the resource instead
                        # "res_model": "llm.knowledge.collection",
                        # "res_id": collection.id,
                    }
                )

                # Create RAG resource using model_id
                resource = self.env["llm.resource"].create( # Target llm.resource
                    {
                        "name": resource_name,
                        "model_id": attachment_model_id,
                        "res_id": attachment.id,
                        "collection_ids": [(4, collection.id)], # Link to collection
                        "retriever": "http", # Specify HTTP retriever
                    }
                )

                # Process resource if requested (full RAG pipeline)
                if self.process_immediately:
                    resource.process_resource() # Calls overridden method

                created_resources |= resource

        # Update wizard state
        self.write(
            {
                "state": "done",
                "created_resource_ids": [(6, 0, created_resources.ids)], # Use renamed field
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name, # Use self._name for correct wizard model
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    # Method renamed for clarity
    def action_view_resources(self):
        """Open the created resources"""
        return {
            "name": "Uploaded RAG Resources",
            "type": "ir.actions.act_window",
            "res_model": "llm.resource", # Target llm.resource
            "view_mode": "tree,form,kanban",
            "domain": [("id", "in", self.created_resource_ids.ids)], # Use renamed field
             # Use the specific views defined in llm_knowledge for llm.resource
            "view_ids": [(5, 0, 0),
                (0, 0, {'view_mode': 'kanban', 'view_id': self.env.ref('llm_knowledge.view_llm_resource_kanban').id}),
                (0, 0, {'view_mode': 'tree', 'view_id': self.env.ref('llm_knowledge.view_llm_resource_tree').id}),
                (0, 0, {'view_mode': 'form', 'view_id': self.env.ref('llm_knowledge.view_llm_resource_form').id})],
            "search_view_id": [self.env.ref('llm_knowledge.view_llm_resource_search').id],
        }