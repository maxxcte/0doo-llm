import logging
import re

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class UploadResourceWizard(models.TransientModel):
    _name = "llm.upload.resource.wizard"
    _description = "Upload Resources Wizard"

    file_ids = fields.Many2many(
        "ir.attachment", string="Files", help="Local files to upload"
    )
    external_urls = fields.Text(
        string="External URLs", help="External URLs to include, one per line"
    )
    resource_name_template = fields.Char(
        string="Resource Name Template",
        default="{filename}",
        help="Template for resource names. Use {filename} and {index} as placeholders.",
        required=True,
    )
    process_immediately = fields.Boolean(
        string="Process Immediately",
        default=False,
        help="If checked, resources will be immediately processed through the pipeline",
    )
    state = fields.Selection(
        [
            ("confirm", "Confirm"),
            ("done", "Done"),
        ],
        default="confirm",
    )
    created_resource_ids = fields.Many2many(
        "llm.resource",
        string="Created Resources",
    )
    created_count = fields.Integer(string="Created", compute="_compute_created_count")

    @api.depends("created_resource_ids")
    def _compute_created_count(self):
        for wizard in self:
            wizard.created_count = len(wizard.created_resource_ids)

    def _extract_filename_from_url(self, url):
        """Extract a clean filename from a URL"""
        # Try to extract filename from the URL path
        match = re.search(r"/([^/]+)(?:\?.*)?$", url)
        if match:
            filename = match.group(1)
            # Remove query string if present
            if "?" in filename:
                filename = filename.split("?")[0]
            return filename
        return url

    def action_upload_resources(self):
        """Create resources from uploaded files and external URLs"""
        self.ensure_one()
        created_resources = self.env["llm.resource"]

        # Get the ir.model record for ir.attachment
        attachment_model_id = (
            self.env["ir.model"].search([("model", "=", "ir.attachment")], limit=1).id
        )
        if not attachment_model_id:
            raise UserError(_("Could not find ir.attachment model"))

        # Validate that at least one file or URL is provided
        if not self.file_ids and not self.external_urls:
            raise UserError(_("Please provide at least one file or URL"))

        # Process local files
        for index, attachment in enumerate(self.file_ids):
            resource_name = self.resource_name_template.format(
                filename=attachment.name,
                index=index + 1,
            )

            # Create resource using model_id
            resource = self.env["llm.resource"].create(
                {
                    "name": resource_name,
                    "model_id": attachment_model_id,
                    "res_id": attachment.id,
                }
            )

            # Process resource if requested
            if self.process_immediately:
                resource.process_resource()

            created_resources |= resource

        # Process external URLs
        if self.external_urls:
            urls = [
                url.strip() for url in self.external_urls.split("\n") if url.strip()
            ]
            for index, url in enumerate(urls):
                # Extract filename from URL for naming
                filename = self._extract_filename_from_url(url)

                resource_name = self.resource_name_template.format(
                    filename=filename,
                    index=len(self.file_ids) + index + 1,
                )

                # Create attachment for URL
                attachment = self.env["ir.attachment"].create(
                    {
                        "name": filename,
                        "type": "url",
                        "url": url,
                    }
                )

                # Create resource using model_id
                resource = self.env["llm.resource"].create(
                    {
                        "name": resource_name,
                        "model_id": attachment_model_id,
                        "res_id": attachment.id,
                        "retriever": "http",  # Use HTTP retriever for URLs
                    }
                )

                # Process resource if requested
                if self.process_immediately:
                    resource.process_resource()

                created_resources |= resource

        # Update wizard state
        self.write(
            {
                "state": "done",
                "created_resource_ids": [(6, 0, created_resources.ids)],
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": "llm.upload.resource.wizard",
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
            "context": self.env.context,
        }

    def action_view_resources(self):
        """Open the created resources"""
        return {
            "name": "Uploaded Resources",
            "type": "ir.actions.act_window",
            "res_model": "llm.resource",
            "view_mode": "tree,form,kanban",
            "domain": [("id", "in", self.created_resource_ids.ids)],
        }
