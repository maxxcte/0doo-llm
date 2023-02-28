import json
import logging

from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import ValidationError

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMTool(models.Model):
    _name = "llm.tool"
    _description = "LLM Tool"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, tracking=True)
    description = fields.Text(
        required=True,
        tracking=True,
        help="Description of what the tool does. This will be sent to the LLM.",
    )
    implementation = fields.Selection(
        selection=lambda self: self._selection_implementation(),
        required=True,
        help="The implementation that provides this tool's functionality",
    )
    active = fields.Boolean(default=True)
    schema = fields.Text(compute="_compute_schema", store=True, readonly=True)
    default = fields.Boolean(
        default=False,
        help="Set to true if this is a default tool to be included in all LLM requests",
    )
    override_tool_description = fields.Boolean(
        default=False,
        help="If true, uses the description field as-is instead of any generated description",
    )
    override_tool_schema = fields.Boolean(
        default=False,
        help="If true, uses the overriden_schema field instead of computed schema",
    )
    overriden_schema = fields.Text(
        help="Custom schema to use when override_tool_schema is true"
    )

    server_action_id = fields.Many2one(
        "ir.actions.server",
        string="Related Server Action",
        help="The specific server action this tool will execute",
    )

    requires_user_consent = fields.Boolean(
        default=False,
        help="If true, the user must consent to the execution of this tool",
    )

    def get_pydantic_model(self):
        """Get the Pydantic model for this tool's parameters"""
        result = self._dispatch("get_pydantic_model")
        return result

    @api.depends(
        "implementation",
        "name",
        "description",
        "override_tool_description",
        "server_action_id",
        "requires_user_consent",
    )
    def _compute_schema(self):
        """Compute the JSON schema for this tool"""
        for record in self:
            record.schema = self._generate_schema(record)

    def _generate_schema(self, record):
        """Generate the schema for a tool record with error handling"""
        fallback_schema = self._get_fallback_schema(record)

        if not record.id or not record.implementation:
            _logger.info(
                f"No id or implementation for {record.name}, using default schema"
            )
            return fallback_schema

        try:
            pydantic_model = record.get_pydantic_model()
            if not pydantic_model:
                return fallback_schema

            tool_schema = convert_to_openai_tool(pydantic_model)

            # Add consent information to the description if required
            description = record.description
            if record.requires_user_consent:
                fallback_consent_warning = "\n\nIMPORTANT: This tool requires explicit user consent before execution. Please ask the user for permission before using this tool."
                # Get consent message from config
                config = self.env["llm.tool.consent.config"].get_active_config()
                consent_warning = (
                    config.tool_description_message or fallback_consent_warning
                )
                description += consent_warning

            # Override description if needed or add consent warning
            if record.override_tool_description or record.requires_user_consent:
                tool_schema["function"]["description"] = description

            return json.dumps(tool_schema)
        except Exception as e:
            _logger.exception(f"Error computing schema for {record.name}: {str(e)}")
            return fallback_schema

    def _get_fallback_schema(self, record):
        """Get a fallback schema when the normal schema generation fails"""
        schema = {
            "type": "function",
            "function": {
                "name": record.name or "unnamed_tool",
                "description": record.description or "",
                "parameters": {},
            },
        }
        return json.dumps(schema)

    def execute(self, parameters):
        """Execute this tool with the given parameters"""
        # Validate parameters if a Pydantic model is available
        validated_parameters = self._validate_parameters(parameters)
        return self._dispatch("execute", validated_parameters)

    def _validate_parameters(self, parameters):
        """Validate parameters against the Pydantic model"""
        pydantic_model = self.get_pydantic_model()
        if not pydantic_model:
            return parameters

        try:
            validated_params = pydantic_model(**parameters)
            return validated_params.model_dump()
        except ValidationError as e:
            raise UserError(_("Invalid parameters: %s") % str(e)) from e

    def _dispatch(self, method, *args, **kwargs):
        """Dispatch method call to appropriate implementation"""
        if not self.implementation:
            raise UserError(_("Tool implementation not configured"))

        implementation_method = f"{self.implementation}_{method}"
        if not hasattr(self, implementation_method):
            raise NotImplementedError(
                _("Method %s not implemented for implementation %s")
                % (method, self.implementation)
            )

        return getattr(self, implementation_method)(*args, **kwargs)

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

    def _parse_json_safely(self, json_string, default_value=None):
        """Parse JSON with error handling"""
        try:
            return json.loads(json_string)
        except json.JSONDecodeError as e:
            _logger.error(f"Invalid JSON for tool {self.name}: {str(e)}")
            return default_value

    def to_tool_definition(self):
        """Convert this tool to an OpenAI-compatible tool definition"""
        # Determine which schema to use
        if self.override_tool_schema and self.overriden_schema:
            schema_json = self.overriden_schema
        else:
            schema_json = self.schema

        # Parse the schema with error handling
        result = self._parse_json_safely(schema_json, self._get_fallback_schema_dict())

        # Override description if needed
        if self.override_tool_description and "function" in result:
            result["function"]["description"] = self.description

        return result

    def _get_fallback_schema_dict(self):
        """Get a fallback schema as a dictionary"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description
                if self.override_tool_description
                else "Default tool description",
                "parameters": {},
            },
        }
