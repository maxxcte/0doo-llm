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
    service = fields.Selection(
        selection=lambda self: self._selection_service(),
        required=True,
        help="The service that implements this tool",
    )
    active = fields.Boolean(default=True)
    schema = fields.Text(
        required=True, 
        help="JSON Schema for the tool parameters in JSON format"
    )
    default = fields.Boolean(
        default=False,
        help="Set to true if this is a default tool to be included in all LLM requests"
    )
    
    # Computed field to validate schema
    schema_valid = fields.Boolean(compute="_compute_schema_valid", store=False)
    schema_error = fields.Char(compute="_compute_schema_valid", store=False)
    
    @api.depends('schema')
    def _compute_schema_valid(self):
        for record in self:
            record.schema_valid = True
            record.schema_error = False
            
            try:
                if record.schema:
                    json.loads(record.schema)
            except json.JSONDecodeError as e:
                record.schema_valid = False
                record.schema_error = str(e)
    
    def _dispatch(self, method, *args, **kwargs):
        """Dispatch method call to appropriate service implementation"""
        if not self.service:
            raise UserError(_("Tool service not configured"))

        service_method = f"{self.service}_{method}"
        if not hasattr(self, service_method):
            raise NotImplementedError(
                _("Method %s not implemented for service %s") % (method, self.service)
            )

        return getattr(self, service_method)(*args, **kwargs)
    
    @api.model
    def _selection_service(self):
        """Get all available services from tool implementations"""
        services = []
        for service in self._get_available_services():
            services.append(service)
        return services
    
    @api.model
    def _get_available_services(self):
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