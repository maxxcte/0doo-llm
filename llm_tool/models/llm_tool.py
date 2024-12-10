import inspect
import json
import logging
from typing import Any, get_type_hints

from pydantic import create_model

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMTool(models.Model):
    _name = "llm.tool"
    _description = "LLM Tool"
    _inherit = ["mail.thread"]

    # Basic tool information
    name = fields.Char(
        required=True,
        tracking=True,
        help="The name of the tool. This will be used by the LLM to call the tool.",
    )
    description = fields.Text(
        required=True,
        tracking=True,
        help="A human-readable description of what the tool does. This will be sent to the LLM.",
    )
    implementation = fields.Selection(
        selection=lambda self: self._selection_implementation(),
        required=True,
        help="The implementation that provides this tool's functionality",
    )
    active = fields.Boolean(default=True)

    # Input schema
    input_schema = fields.Text(
        string="Input Schema",
        help="JSON Schema defining the expected parameters for the tool",
    )

    # Annotations (following the schema specification)
    title = fields.Char(string="Title", help="A human-readable title for the tool")
    read_only_hint = fields.Boolean(
        string="Read Only",
        default=False,
        help="If true, the tool does not modify its environment",
    )
    idempotent_hint = fields.Boolean(
        string="Idempotent",
        default=False,
        help="If true, calling the tool repeatedly with the same arguments will have no additional effect",
    )
    destructive_hint = fields.Boolean(
        string="Destructive",
        default=True,
        help="If true, the tool may perform destructive updates to its environment",
    )
    open_world_hint = fields.Boolean(
        string="Open World",
        default=True,
        help="If true, this tool may interact with an 'open world' of external entities",
    )

    # Implementation-specific fields
    server_action_id = fields.Many2one(
        "ir.actions.server",
        string="Related Server Action",
        help="The specific server action this tool will execute",
    )

    # User consent
    requires_user_consent = fields.Boolean(
        default=False,
        help="If true, the user must consent to the execution of this tool",
    )

    # Default tool flag
    default = fields.Boolean(
        default=False,
        help="Set to true if this is a default tool to be included in all LLM requests",
    )

    @api.model
    def _selection_implementation(self):
        """Get all available implementations from tool implementations"""
        implementations = []
        for implementation in self._get_available_implementations():
            implementations.append(implementation)
        return implementations

    @api.model
    def _get_available_implementations(self):
        """Hook method for registering tool services"""
        return []

    def get_pydantic_model_from_signature(self, method):
        """Create a Pydantic model from a method signature"""
        type_hints = get_type_hints(method)
        signature = inspect.signature(method)
        fields = {}

        for param_name, param in signature.parameters.items():
            if param_name == "self":
                continue
            fields[param_name] = (
                type_hints.get(param_name, Any),
                param.default if param.default != param.empty else ...,
            )

        return create_model("DynamicModel", **fields)

    def get_input_schema(self, method="execute"):
        """Generate input schema from the method signature of the implementation"""
        if not self.implementation:
            return {}

        impl_method_name = f"{self.implementation}_{method}"
        if not hasattr(self, impl_method_name):
            _logger.warning(f"Method {impl_method_name} not found for tool {self.name}")
            return {}

        method = getattr(self, impl_method_name)
        model = self.get_pydantic_model_from_signature(method)
        schema = model.model_json_schema()

        if method.__doc__:
            doc_lines = method.__doc__.split("\n")
            param_desc = {}

            for line in doc_lines:
                line = line.strip()
                for prop_name in schema.get("properties", {}):
                    if line.startswith(f"{prop_name}:"):
                        param_desc[prop_name] = line[len(prop_name) + 1 :].strip()

            for prop_name, desc in param_desc.items():
                if prop_name in schema.get("properties", {}):
                    schema["properties"][prop_name]["description"] = desc

        return schema

    def execute(self, parameters):
        """Execute this tool with validated parameters"""
        if not self.implementation:
            raise UserError(_("Tool implementation not configured"))

        impl_method_name = f"{self.implementation}_execute"
        if not hasattr(self, impl_method_name):
            raise NotImplementedError(
                _("Method execute not implemented for implementation %s")
                % self.implementation
            )

        method = getattr(self, impl_method_name)

        model = self.get_pydantic_model_from_signature(method)
        validated = model(**parameters)
        validated_dict = validated.model_dump()
        return method(**validated_dict)

    # API methods for the Tool schema
    def get_tool_definition(self):
        """Returns a Tool object as per the schema specification"""
        self.ensure_one()

        # Get the input schema - either from input_schema field or compute it
        input_schema_data = {}
        if self.input_schema:
            try:
                input_schema_data = json.loads(self.input_schema)
            except (json.JSONDecodeError, TypeError):
                # If we can't parse the input_schema, generate it from the method signature
                input_schema_data = self.get_input_schema()
        else:
            # Generate schema from method signature
            input_schema_data = self.get_input_schema()

        # If we still don't have a schema, use a default
        if not input_schema_data:
            input_schema_data = {"type": "object", "properties": {}, "required": []}

        # Build annotations object
        annotations = {
            "title": self.title if self.title else self.name,
            "readOnlyHint": self.read_only_hint,
            "idempotentHint": self.idempotent_hint,
            "destructiveHint": self.destructive_hint,
            "openWorldHint": self.open_world_hint,
        }

        # Build tool definition matching the schema
        tool_def = {
            "name": self.name,
            "description": self.description,
            "inputSchema": input_schema_data,
            "annotations": annotations,
        }

        return tool_def

    @api.onchange("implementation")
    def _onchange_implementation(self):
        """When implementation changes and input_schema is empty, populate it with the implementation schema"""
        if self.implementation and not self.input_schema:
            schema = self.get_input_schema()
            if schema:
                self.input_schema = json.dumps(schema, indent=2)

    def action_reset_input_schema(self):
        """Reset the input schema to the implementation schema"""
        for record in self:
            schema = record.get_input_schema()
            if schema:
                record.input_schema = json.dumps(schema, indent=2)
        # Return an action to reload the view
        return {
            "type": "ir.actions.client",
            "tag": "reload",
        }
