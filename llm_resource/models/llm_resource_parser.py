import json
import logging

from odoo import _, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMResourceParser(models.Model):
    _inherit = "llm.resource"

    def parse(self):
        """Parse the retrieved content to markdown"""
        for resource in self:
            if resource.state != "retrieved":
                _logger.warning(
                    "Resource %s must be in retrieved state to parse content",
                    resource.id,
                )
                continue

        # Lock resources and process only the successfully locked ones
        resources = self._lock()
        if not resources:
            return False

        try:
            # Process each resource
            for resource in resources:
                try:
                    # Get the related record
                    record = self.env[resource.res_model].browse(resource.res_id)
                    if not record.exists():
                        raise UserError(_("Referenced record not found"))

                    # If the record has a specific rag_parse method, call it
                    if hasattr(record, "rag_parse"):
                        success = record.rag_parse(resource)
                    else:
                        # Use appropriate parser based on selection
                        if resource.parser == "default":
                            success = resource._parse_default(record)
                        elif resource.parser == "json":
                            success = resource._parse_json(record)
                        else:
                            _logger.warning(
                                "Unknown parser %s, falling back to default",
                                resource.parser,
                            )
                            success = resource._parse_default(record)

                    # Only update state if parsing was successful
                    if success:
                        # Debug logging
                        _logger.info(
                            "Parsing successful for resource %s, updating state to 'parsed'",
                            resource.id,
                        )

                        # Explicitly commit the state change to ensure it's saved
                        resource.write({"state": "parsed"})
                        self.env.cr.commit()  # Force commit the transaction

                        resource._post_message(
                            "Resource successfully parsed", "success"
                        )
                    else:
                        resource._post_message(
                            "Parsing completed but did not return success", "warning"
                        )

                except Exception as e:
                    _logger.error(
                        "Error parsing resource %s: %s",
                        resource.id,
                        str(e),
                        exc_info=True,
                    )
                    resource._post_message(f"Error parsing resource: {str(e)}", "error")
                    resource._unlock()

            # Unlock all successfully processed resources
            resources._unlock()
            return True

        except Exception as e:
            resources._unlock()
            raise UserError(_("Error in batch parsing: %s") % str(e)) from e

    def _parse_default(self, record):
        """
        Default parser implementation - generates a generic markdown representation
        based on commonly available fields
        """
        self.ensure_one()

        # Start with the record name/display_name if available
        record_name = (
            record.display_name
            if hasattr(record, "display_name")
            else f"{record._name} #{record.id}"
        )
        content = [f"# {record_name}"]

        # Try to include description or common text fields
        common_text_fields = [
            "description",
            "note",
            "comment",
            "message",
            "content",
            "body",
            "text",
        ]
        for field_name in common_text_fields:
            if hasattr(record, field_name) and record[field_name]:
                content.append(f"\n## {field_name.capitalize()}\n")
                content.append(record[field_name])

        # Include a basic info section with simple fields
        info_items = []
        for field_name, field in record._fields.items():
            # Skip binary fields, one2many, many2many, and already included text fields
            if (
                field.type in ["binary", "one2many", "many2many"]
                or field_name in common_text_fields
            ):
                continue

            # Skip technical and internal fields
            if field_name.startswith("_") or field_name in [
                "id",
                "display_name",
                "create_date",
                "create_uid",
                "write_date",
                "write_uid",
            ]:
                continue

            # Get value if it exists and is not empty
            value = record[field_name]
            if value or value == 0:  # Include 0 but not False or None
                if field.type == "many2one" and value:
                    value = value.display_name
                info_items.append(f"- **{field.string}**: {value}")

        if info_items:
            content.append("\n## Information\n")
            content.extend(info_items)

        # Set the content
        self.content = "\n".join(content)

        # Post success message
        self._post_message(
            f"Resource parsed using default parser for {record._name}", "success"
        )

        return True

    def _parse_json(self, record):
        """
        JSON parser implementation - converts record data to JSON and then to markdown
        """
        self.ensure_one()

        # Get record name or default to model name and ID
        record_name = (
            record.display_name
            if hasattr(record, "display_name")
            else f"{record._name} #{record.id}"
        )

        # Create a dictionary with record data
        record_data = {}
        for field_name, field in record._fields.items():
            # Skip binary fields and internal fields
            if field.type == "binary" or field_name.startswith("_"):
                continue

            # Handle many2one fields
            if field.type == "many2one" and record[field_name]:
                record_data[field_name] = {
                    "id": record[field_name].id,
                    "name": record[field_name].display_name,
                }
            # Handle many2many and one2many fields
            elif field.type in ["many2many", "one2many"]:
                record_data[field_name] = [
                    {"id": r.id, "name": r.display_name} for r in record[field_name]
                ]
            # Handle other fields
            else:
                record_data[field_name] = record[field_name]

        # Format as markdown
        content = [f"# {record_name}"]
        content.append("\n## JSON Data\n")
        content.append("```json")
        content.append(json.dumps(record_data, indent=2, default=str))
        content.append("```")

        # Update resource content
        self.content = "\n".join(content)

        # Post success message
        self._post_message(
            f"Resource parsed using JSON parser for {record._name}", "success"
        )

        return True
