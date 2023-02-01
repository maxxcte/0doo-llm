import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import AccessError
from pydantic import BaseModel, Field, ConfigDict
from langchain_core.utils.function_calling import convert_to_openai_tool
_logger = logging.getLogger(__name__)

class LLMToolServerAction(models.Model):
    _inherit = "llm.tool"
    
    # Add a field to store the bound server action
    server_action_id = fields.Many2one(
        'ir.actions.server', string='Related Server Action',
        help='The specific server action this tool will execute'
    )
    schema = fields.Text(compute='_compute_schema', store=True, readonly=True)

    @api.depends('implementation', 'name', 'description', 'server_action_id')
    def _compute_schema(self):
        _logger.info("server_action_id: %s", self.server_action_id)
        for record in self:
            # Only attempt to get schema for existing records with implementation
            if record.id and record.implementation:
                try:
                    pydantic_model = record.get_pydantic_model()
                    _logger.info("Pydantic model: %s", pydantic_model)
                    if pydantic_model:
                        schema_dict = convert_to_openai_tool(pydantic_model)
                        _logger.info("Schema dict: %s", schema_dict)
                        record.schema = json.dumps(schema_dict)
                    else:
                        record.schema = '{}'
                except Exception:
                    record.schema = '{}'
            else:
                record.schema = '{}'

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [
            ("server_action", "Odoo Server Action")
        ]
        
    def server_action_get_pydantic_model(self):
        _logger.info("server_action_get_pydantic_model called")
        if not self.server_action_id:
            _logger.info("No server action selected")
            return None
        class ServerActionParams(BaseModel):
            """This function takes the parameters required for server action, including context and record_id and executes it"""
            model_config = ConfigDict(
                title = self.name or "odoo_server_action",
            )
            context: dict = Field(default={}, description="Additional context variables for the action, this field is optional")
            record_id: int = Field(default=None, description="ID of the record to set as active_id")
                
        return ServerActionParams

    @api.onchange('server_action_id')
    def _onchange_server_action_id(self):
        """Update tool name and description based on the selected server action"""
        if self.server_action_id and self.implementation == 'server_action':
            # Generate a suitable name if not already set
            if not self.name or self.name.startswith('run_'):
                action_name = self.server_action_id.name.lower().replace(' ', '_')
                self.name = f"run_{action_name}"
            
            # Update description if not manually set
            if not self.description or 'This action works on the' in self.description:
                self.description = (
                    f"Run the '{self.server_action_id.name}' server action. "
                    f"This action works on the '{self.server_action_id.model_id.name}' model."
                )
        elif self.server_action_id and self.implementation != 'server_action':
            self.server_action_id = None
    
    
    # Implementation of the Odoo Server Action tool
    def server_action_execute(self, parameters):
        """Execute an Odoo Server Action tool
        
        Parameters:
            - record_id: Optional record ID to set as active_id
            - context: Optional context variables for the action
        """
        _logger.info(f"Executing Odoo Server Action with parameters: {parameters}")
        
        # Use the bound server action
        if not self.server_action_id:
            return {"error": "No server action is bound to this tool"}
            
        server_action = self.server_action_id
        record_id = parameters.get('record_id')
        context = parameters.get('context', {})
        
        try:
            # Check access rights
            if server_action.groups_id and not (server_action.groups_id & self.env.user.groups_id):
                return {"error": "You don't have enough access rights to run this action"}
            
            # Prepare execution context
            action_context = {}
            
            # Add active_id and active_model if provided
            if record_id:
                model = server_action.model_id.model
                
                # Validate record existence
                record = self.env[model].browse(record_id)
                if not record.exists():
                    return {"error": f"Record with ID {record_id} not found in model {model}"}
                
                # Check access rights on the record
                try:
                    record.check_access_rights('write')
                    record.check_access_rule('write')
                except AccessError:
                    return {"error": f"Access denied to record {record_id} of model {model}"}
                
                action_context.update({
                    'active_id': record_id,
                    'active_model': model,
                    'active_ids': [record_id],
                })
            
            # Add any additional context provided, sanitizing it first
            if context:
                safe_context = {k: v for k, v in context.items() 
                              if not k.startswith('_') and k not in ('uid', 'su')}
                action_context.update(safe_context)
            
            # Add audit logging
            _logger.info(
                f"LLM executing server action: id={server_action.id}, name='{server_action.name}', "
                f"model='{server_action.model_id.model}', record_id={record_id}, user={self.env.user.name}"
            )
            
            # Execute the server action with the prepared context
            result = server_action.with_context(**action_context).run()
            
            # Return the result (may be an action to execute)
            if result:
                # If result is an action dictionary, convert to JSON serializable
                return json.loads(json.dumps(result, default=str))
            else:
                return {"success": True, "message": f"Server action '{server_action.name}' executed successfully"}
                
        except Exception as e:
            _logger.exception(f"Error executing Server Action: {str(e)}")
            return {"error": str(e)}