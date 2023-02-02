import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from pydantic import ValidationError
from langchain_core.utils.function_calling import convert_to_openai_tool

_logger = logging.getLogger(__name__)

class LLMTool(models.Model):
    _name = "llm.tool"
    _description = "LLM Tool"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, tracking=True)
    description = fields.Text(required=True, tracking=True, 
                             help="Description of what the tool does. This will be sent to the LLM.")
    implementation = fields.Selection(
        selection=lambda self: self._selection_implementation(),
        required=True,
        help="The implementation that provides this tool's functionality",
    )
    active = fields.Boolean(default=True)
    schema = fields.Text(compute='_compute_schema', store=True, readonly=True)
    default = fields.Boolean(
        default=False,
        help="Set to true if this is a default tool to be included in all LLM requests"
    )
    override_tool_description = fields.Boolean(
        default=False,
        help="If true, uses the description field as-is instead of any generated description"
    )
    override_tool_schema = fields.Boolean(
        default=False,
        help="If true, uses the overriden_schema field instead of computed schema"
    )
    overriden_schema = fields.Text(
        help="Custom schema to use when override_tool_schema is true"
    )

    server_action_id = fields.Many2one(
        'ir.actions.server', string='Related Server Action',
        help='The specific server action this tool will execute'
    )

    requires_user_consent = fields.Boolean(
        default=False,
        help="If true, the user must consent to the execution of this tool"
    )

    def get_pydantic_model(self):
        result = self._dispatch("get_pydantic_model")
        return result

    @api.depends('implementation', 'name', 'description', 'override_tool_description','server_action_id')
    def _compute_schema(self):
        for record in self:
            if record.id and record.implementation:
                try:
                    pydantic_model = record.get_pydantic_model()
                    if pydantic_model:
                        tool_schema = convert_to_openai_tool(pydantic_model)
                        if record.override_tool_description:
                            tool_schema["function"]["description"] = record.description
                        record.schema = json.dumps(tool_schema)
                    else:
                        record.schema = json.dumps({
                            "type": "function",
                            "function": {
                                "name": record.name,
                                "description": record.description,
                                "parameters": {},
                            }
                        })
                except Exception as e:
                    _logger.exception(f"Error computing schema for {record.name}: {str(e)}")
                    record.schema = json.dumps({
                        "type": "function",
                        "function": {
                            "name": record.name,
                            "description": record.description,
                            "parameters": {},
                        }
                    })
            else:
                record.schema = json.dumps({
                    "type": "function",
                    "function": {
                        "name": record.name or "unnamed_tool",
                        "description": record.description or "",
                        "parameters": {},
                    }
                })
            _logger.info(f"No id or impl for {record.name}, stored default schema")
    
    def execute(self, parameters):
        pydantic_model = self.get_pydantic_model()
        if pydantic_model:
            try:
                validated_params = pydantic_model(**parameters)
                return self._dispatch("execute", validated_params.model_dump())
            except ValidationError as e:
                raise UserError(_("Invalid parameters: %s") % str(e))
        return self._dispatch("execute", parameters)
    
    def _dispatch(self, method, *args, **kwargs):
        """Dispatch method call to appropriate implementation"""
        if not self.implementation:
            raise UserError(_("Tool implementation not configured"))
        implementation_method = f"{self.implementation}_{method}"
        if not hasattr(self, implementation_method):
            raise NotImplementedError(
                _("Method %s not implemented for implementation %s") % (method, self.implementation)
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
    
    def to_tool_definition(self):
        try:
            # If schema override is enabled and we have an overriden schema
            if self.override_tool_schema and self.overriden_schema:
                result = json.loads(self.overriden_schema)
            else:
                # Use the computed schema
                result = json.loads(self.schema)
            
            if self.override_tool_description and "function" in result:
                result["function"]["description"] = self.description

            return result
        except json.JSONDecodeError as e:
            _logger.error(f"Invalid schema for tool {self.name}: {str(e)}")
            # Fallback to basic schema
            result = {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": self.description if self.override_tool_description else "Default tool description",
                    "parameters": {},
                }
            }
            _logger.info(f"Falling back to default schema for {self.name}: {json.dumps(result)}")
            return result