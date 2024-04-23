from odoo import api, fields, models, _
from odoo.exceptions import UserError


class LLMProvider(models.Model):
    _inherit = "llm.provider"

    # Add prompt-related fields and methods to the provider
    prompt_ids = fields.Many2many(
        "llm.prompt",
        string="Available Prompts",
        help="Prompts available for this provider",
    )
    
    def list_prompts(self):
        """List all available prompts in MCP format"""
        self.ensure_one()
        
        # Get all active prompts (either explicitly added to this provider or all if none added)
        domain = [("active", "=", True)]
        if self.prompt_ids:
            domain.append(("id", "in", self.prompt_ids.ids))
        
        prompts = self.env["llm.prompt"].search(domain)
        
        # Format in MCP-compatible structure
        return [prompt.get_prompt_data() for prompt in prompts]
    
    def get_prompt(self, name, arguments=None):
        """
        Get a specific prompt with the given arguments
        
        Args:
            name (str): Name of the prompt to get
            arguments (dict): Dictionary of argument values
            
        Returns:
            dict: MCP-compatible prompt result
        """
        # Find the prompt
        domain = [("name", "=", name), ("active", "=", True)]
        if self.prompt_ids:
            domain.append(("id", "in", self.prompt_ids.ids))
        
        prompt = self.env["llm.prompt"].search(domain, limit=1)
        if not prompt:
            raise UserError(_("Prompt not found: %s") % name)
        
        # Validate arguments
        if arguments:
            for arg in prompt.argument_ids.filtered(lambda a: a.required):
                if arg.name not in arguments:
                    raise UserError(_("Missing required argument: %s") % arg.name)
                
                # Validate the argument value
                is_valid, error_message = arg.validate_value(arguments[arg.name])
                if not is_valid:
                    raise UserError(_("Invalid argument %s: %s") % (arg.name, error_message))
        
        # Generate messages
        messages = prompt.get_messages(arguments)
        
        # Return in MCP format
        return {
            "messages": messages,
            "description": prompt.description or "",
        }
