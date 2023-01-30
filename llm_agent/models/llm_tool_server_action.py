import json
import logging
from odoo import api, fields, models, _
from odoo.exceptions import UserError, AccessError

_logger = logging.getLogger(__name__)

class LLMToolServerAction(models.Model):
    _inherit = "llm.tool"
    
    # Add a field to store the bound server action
    server_action_id = fields.Many2one(
        'ir.actions.server', string='Bound Server Action',
        help='The specific server action this tool will execute'
    )
    
    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [
            ("server_action", "Odoo Server Action")
        ]
    
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
            
            # Update schema based on the action type
            self._update_schema_for_server_action()
    
    def _update_schema_for_server_action(self):
        """Update the JSON schema based on the server action type"""
        if not self.server_action_id:
            return
            
        schema = {
            "type": "object",
            "properties": {}
        }
        
        # All server actions can accept a context
        schema["properties"]["context"] = {
            "type": "object",
            "description": "Additional context variables for the action"
        }
        
        # Add model-specific properties if it's not a multi-action
        if self.server_action_id.state != 'multi':
            # Add model and record_id fields
            schema["properties"]["record_id"] = {
                "type": "integer",
                "description": f"ID of the record to set as active_id"
            }
            
            # If it's a write or create action, it might need more specific fields
            if self.server_action_id.state in ['object_write', 'object_create']:
                # We might add specific fields here based on the model fields
                pass
        
        self.schema = json.dumps(schema, indent=2)
    
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