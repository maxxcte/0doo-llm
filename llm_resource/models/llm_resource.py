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

    @api.depends("res_model", "res_id")
    def _compute_external_url(self):
        for resource in self:
            resource.external_url = False
            if not resource.res_model or not resource.res_id:
                continue

            resource.external_url = self._get_record_external_url(
                resource.res_model, resource.res_id
            )

    def _get_record_external_url(self, res_model, res_id):
        """
        Get the external URL for a record based on its model and ID.

        This method can be extended by other modules to support additional models.

        :param res_model: The model name
        :param res_id: The record ID
        :return: The external URL or False
        """
        try:
            # Get the related record
            if res_model in self.env:
                record = self.env[res_model].browse(res_id)
                if not record.exists():
                    return False

                # Case 1: Handle ir.attachment with type 'url'
                if res_model == "ir.attachment" and hasattr(record, "type"):
                    if record.type == "url" and hasattr(record, "url"):
                        return record.url

                # Case 2: Check if record has an external_url field
                elif hasattr(record, "external_url"):
                    return record.external_url

        except Exception as e:
            _logger.warning(
                "Error computing external URL for resource model %s, id %s: %s",
                res_model,
                res_id,
                str(e),
            )

        return False

    @api.depends("lock_date")
    def _compute_kanban_state(self):
        for record in self:
            record.kanban_state = "blocked" if record.lock_date else "normal"

    def _lock(self, state_filter=None, stale_lock_minutes=10):
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
        if state_filter:
            domain.append(("state", "=", state_filter))

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

    def action_open_resource(self):
        """Open the resource in form view."""
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "res_model": "llm.resource",
            "res_id": self.id,
            "view_mode": "form",
            "target": "current",
        }

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
        result = resources.process_resource()
        if result:
            return {
                "type": "ir.actions.client",
                "tag": "reload",
            }

        else:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Processing Failed"),
                    "message": _("Mass processing resources failed"),
                    "sticky": False,
                    "type": "danger",
                },
            }

    def action_mass_unlock(self):
        """
        Mass unlock action for the server action.
        """
        # Unlock the resources
        self._unlock()

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Resources Unlocked"),
                "message": _("%s resources have been unlocked") % len(self),
                "sticky": False,
                "type": "success",
            },
        }

    def action_mass_reset(self):
        """
        Mass reset action for the server action.
        Resets all non-draft resources back to draft state.
        """
        # Get active IDs from context
        active_ids = self.env.context.get("active_ids", [])
        if not active_ids:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Resources Selected"),
                    "message": _("Please select resources to reset."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        resources = self.browse(active_ids)
        # Filter resources that are not in draft state
        non_draft_resources = resources.filtered(lambda r: r.state != "draft")

        if not non_draft_resources:
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("No Resources Reset"),
                    "message": _("No resources found that need resetting."),
                    "type": "warning",
                    "sticky": False,
                },
            }

        # Reset resources to draft state and unlock them
        non_draft_resources.write(
            {
                "state": "draft",
                "lock_date": False,
            }
        )

        # Reload the view to reflect changes
        return {
            "type": "ir.actions.client",
            "tag": "reload",
            "params": {
                "menu_id": self.env.context.get("menu_id"),
                "action": self.env.context.get("action"),
            },
        }
