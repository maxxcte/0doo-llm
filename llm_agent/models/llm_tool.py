import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError

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
    schema = fields.Text(
        help="JSON Schema for the tool parameters in JSON format"
    )
    default = fields.Boolean(
        default=False,
        help="Set to true if this is a default tool to be included in all LLM requests"
    )
    
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
    
    def execute(self, parameters):
        """Execute the tool with the given parameters"""
        return self._dispatch("execute", parameters)
    
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