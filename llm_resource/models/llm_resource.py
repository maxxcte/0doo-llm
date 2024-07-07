import logging
from datetime import timedelta

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)


class LLMResource(models.Model):
    _name = "llm.resource"
    _description = "LLM Resource for Document Management"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "id desc"
    _sql_constraints = [
        (
            "unique_resource_reference",
            "UNIQUE(model_id, res_id)",
            "A resource already exists for this record. Please use the existing resource.",
        ),
    ]

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
    )
    model_id = fields.Many2one(
        "ir.model",
        string="Related Model",
        required=True,
        tracking=True,
        ondelete="cascade",
        help="The model of the referenced document",
    )
    res_model = fields.Char(
        string="Model Name",
        related="model_id.model",
        store=True,
        readonly=True,
        help="Technical name of the related model",
    )
    res_id = fields.Integer(
        string="Record ID",
        required=True,
        tracking=True,
        help="The ID of the referenced record",
    )
    content = fields.Text(
        string="Content",
        help="Markdown representation of the resource content",
    )
    external_url = fields.Char(
        string="External URL",
        compute="_compute_external_url",
        store=True,
        help="External URL from the related record if available",
    )
    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("retrieved", "Retrieved"),
            ("parsed", "Parsed"),
        ],
        string="State",
        default="draft",
        tracking=True,
    )
    lock_date = fields.Datetime(
        string="Lock Date",
        tracking=True,
        help="Date when the resource was locked for processing",
    )
    kanban_state = fields.Selection(
        [
            ("normal", "Ready"),
            ("blocked", "Blocked"),
            ("done", "Done"),
        ],
        string="Kanban State",
        compute="_compute_kanban_state",
        store=True,
    )
    
    # Selection fields for retrievers and parsers
    retriever = fields.Selection(
        selection="_get_available_retrievers",
        string="Retriever",
        default="default",
        required=True,
        help="Method used to retrieve resource content",
        tracking=True,
    )
    parser = fields.Selection(
        selection="_get_available_parsers",
        string="Parser",
        default="default",
        required=True,
        help="Method used to parse resource content",
        tracking=True,
    )

    @api.model
    def _get_available_retrievers(self):
        """Get all available retriever methods"""
        return [("default", "Default Retriever")]
        
    @api.model
    def _get_available_parsers(self):
        """Get all available parser methods"""
        return [
            ("default", "Default Parser"),
            ("json", "JSON Parser"),
        ]

    @api.depends("res_model", "res_id")
    def _compute_external_url(self):
        """Compute external URL from related record if available"""
        for resource in self:
            resource.external_url = False
            if not resource.res_model or not resource.res_id:
                continue

            try:
                # Get the related record
                if resource.res_model in self.env:
                    record = self.env[resource.res_model].browse(resource.res_id)
                    if not record.exists():
                        continue

                    # Case 1: Handle ir.attachment with type 'url'
                    if resource.res_model == "ir.attachment" and hasattr(
                        record, "type"
                    ):
                        if record.type == "url" and hasattr(record, "url"):
                            resource.external_url = record.url

                    # Case 2: Check if record has an external_url field
                    elif hasattr(record, "external_url"):
                        resource.external_url = record.external_url

            except Exception as e:
                _logger.warning(
                    "Error computing external URL for resource %s: %s",
                    resource.id,
                    str(e),
                )
                continue

    @api.depends("lock_date")
    def _compute_kanban_state(self):
        for record in self:
            record.kanban_state = "blocked" if record.lock_date else "normal"

    def _post_message(self, message, message_type="info"):
        """
        Post a message to the resource's chatter with appropriate styling.

        Args:
            message (str): The message to post
            message_type (str): Type of message (error, warning, success, info)
        """
        if message_type == "error":
            body = f"<p class='text-danger'><strong>Error:</strong> {message}</p>"
        elif message_type == "warning":
            body = f"<p class='text-warning'><strong>Warning:</strong> {message}</p>"
        elif message_type == "success":
            body = f"<p class='text-success'><strong>Success:</strong> {message}</p>"
        else:  # info
            body = f"<p><strong>Info:</strong> {message}</p>"

        return self.message_post(
            body=body,
            message_type="comment",
        )

    def _lock(self, stale_lock_minutes=10):
        """Lock resources for processing and return the ones successfully locked"""
        now = fields.Datetime.now()
        stale_lock_threshold = now - timedelta(minutes=stale_lock_minutes)

        # Find resources that are not locked or have stale locks
        domain = [
            ("id", "in", self.ids),
            "|",
            ("lock_date", "=", False),
            ("lock_date", "<", stale_lock_threshold),
        ]

        unlocked_docs = self.env["llm.resource"].search(domain)

        if unlocked_docs:
            unlocked_docs.write({"lock_date": now})

        return unlocked_docs

    def _unlock(self):
        """Unlock resources after processing"""
        return self.write({"lock_date": False})

    def process_resource(self):
        """
        Process resources through retrieval and parsing.
        Can handle multiple resources at once, processing them through
        as many pipeline stages as possible based on their current states.
        """
        # Stage 1: Retrieve content for draft resources
        draft_docs = self.filtered(lambda d: d.state == "draft")
        if draft_docs:
            draft_docs.retrieve()

        # Stage 2: Parse retrieved resources
        retrieved_docs = self.filtered(lambda d: d.state == "retrieved")
        if retrieved_docs:
            retrieved_docs.parse()

        return True

    @api.model
    def action_mass_process_resources(self):
        """
        Server action handler for mass processing resources.
        This will be triggered from the server action in the UI.
        """
        active_ids = self.env.context.get("active_ids", [])
        if not active_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Resources Selected"),
                    "message": _("Please select resources to process."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        resources = self.browse(active_ids)
        # Process all selected resources
        resources.process_resource()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Resource Processing"),
                "message": _("%s resources processing started") % len(resources),
                "sticky": False,
                "type": "success",
            },
        }
