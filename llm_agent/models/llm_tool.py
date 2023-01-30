import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from pydantic import ValidationError
from langchain_core.utils.function_calling import convert_to_openai_function
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

    def get_pydantic_model(self):
        return self._dispatch("get_pydantic_model")

    @api.depends('implementation')
    def _compute_schema(self):
        for record in self:
            pydantic_model = record.get_pydantic_model()
            if pydantic_model:
                record.schema = convert_to_openai_function(pydantic_model)
            else:
                record.schema = '{}'

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
        """Convert tool to OpenAI compatible tool definition"""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": json.loads(self.schema),
            }
        }