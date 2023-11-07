import logging

from odoo import _, api, fields, models
from odoo.tools import safe_eval

_logger = logging.getLogger(__name__)


class BaseAutomation(models.Model):
    _inherit = "base.automation"

    # We need to extend the selection field properly
    # Cannot directly use selection_add because it needs the original selection
    # Instead, we'll override the field completely
    state = fields.Selection(
        selection=[
            ("code", "Execute Python Code"),
            ("object_create", "Create a new Record"),
            ("object_write", "Update the Record"),
            ("mail_post", "Post a Message"),
            ("followers", "Add Followers"),
            ("next_activity", "Create Next Activity"),
            ("llm_update", "Update LLM Document"),
        ],
        string="Action To Do",
        default="code",
        required=True,
        copy=True,
        help="Type of server action",
    )

    llm_collection_id = fields.Many2one(
        "llm.document.collection",
        string="LLM Collection",
        ondelete="cascade",
        help="LLM Collection that this automated action is linked to",
    )

    llm_auto_process = fields.Boolean(
        string="Auto Process Documents",
        default=True,
        help="Automatically process documents through the RAG pipeline",
    )

    @api.model
    def _get_states(self):
        """Add llm_update to the states dictionary."""
        states = super()._get_states()
        states["llm_update"] = _("Update related LLM document")
        return states

    def _process_llm_update(self, records):
        """Process the update LLM document action."""
        self.ensure_one()

        if not self.llm_collection_id:
            _logger.error("Cannot execute LLM Update action without a collection")
            return False

        collection = self.llm_collection_id
        model_id = self.model_id.id

        # Apply filter_domain to get matched records
        domain = self.filter_domain or "[]"
        matched_records = records

        # If this isn't on_create, we need to filter the records
        if self.trigger != "on_create" and domain != "[]":
            eval_context = self._get_eval_context()
            domain_result = safe_eval.safe_eval(domain, eval_context)
            matched_records = records.filtered_domain(domain_result)

        # Process matched records: either create new or add to collection
        for record in matched_records:
            # Try to find existing document
            existing_doc = self.env["llm.document"].search(
                [("model_id", "=", model_id), ("res_id", "=", record.id)], limit=1
            )

            if existing_doc:
                # If it exists but not in this collection, add it
                if collection.id not in existing_doc.collection_ids.ids:
                    existing_doc.write({"collection_ids": [(4, collection.id)]})
            else:
                # Create a new document
                # Get a meaningful name
                if hasattr(record, "display_name") and record.display_name:
                    name = record.display_name
                elif hasattr(record, "name") and record.name:
                    name = record.name
                else:
                    name = f"{self.model_id.name} #{record.id}"

                # Create the document and add to collection
                doc = self.env["llm.document"].create(
                    {
                        "name": name,
                        "model_id": model_id,
                        "res_id": record.id,
                        "collection_ids": [(4, collection.id)],
                    }
                )

                # Process the document if auto_process is enabled
                if self.llm_auto_process:
                    doc.process_document()

        # For on_write and on_unlink, handle records that no longer match the domain
        if self.trigger in ["on_write", "on_unlink"]:
            unmatched_records = records - matched_records

            for record in unmatched_records:
                # Find document
                doc = self.env["llm.document"].search(
                    [("model_id", "=", model_id), ("res_id", "=", record.id)], limit=1
                )

                if doc and collection.id in doc.collection_ids.ids:
                    # Remove from this collection
                    doc.write({"collection_ids": [(3, collection.id)]})

                    # If document doesn't belong to any collection, remove it
                    if not doc.collection_ids:
                        doc.unlink()

        return True

    def _process(self, records, domain_post=None):
        """Override _process to handle the llm_update state."""
        # Handle standard behavior for other states
        if self.state != "llm_update":
            return super()._process(records, domain_post=domain_post)

        # Filter out the records on which self has already been done
        action_done = self._context.get("__action_done") or {}
        records_done = action_done.get(self, records.browse())
        records -= records_done
        if not records:
            return

        # Mark the remaining records as done (to avoid recursive processing)
        action_done = dict(action_done)
        action_done[self] = records_done + records
        self = self.with_context(__action_done=action_done)
        records = records.with_context(__action_done=action_done)

        # Update document modification date if field exists
        values = {}
        if "date_action_last" in records._fields:
            values["date_action_last"] = fields.Datetime.now()
        if values:
            records.write(values)

        # Process the LLM document update
        self._process_llm_update(records)
