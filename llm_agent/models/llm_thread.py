from odoo import api, fields, models


class LLMThread(models.Model):
    _inherit = "llm.thread"
    
    agent_id = fields.Many2one(
        "llm.agent",
        string="Agent",
        ondelete="restrict",
        help="The agent used for this thread",
    )
    
    @api.onchange("agent_id")
    def _onchange_agent_id(self):
        """Update provider, model and tools when agent changes"""
        if self.agent_id:
            self.provider_id = self.agent_id.provider_id
            self.model_id = self.agent_id.model_id
            self.tool_ids = self.agent_id.tool_ids
    
    def get_assistant_response(self, stream=True, system_prompt=None):
        """Override to include agent's system prompt if agent is set
        
        Args:
            stream (bool): Whether to stream the response
            system_prompt (str, optional): Additional system prompt to include with the agent's system prompt
        
        Yields:
            dict: Response chunks with various types (content, tool_start, tool_end, error)
        """
        # If no agent, use the original method with the provided system prompt
        if not self.agent_id:
            return super().get_assistant_response(stream=stream, system_prompt=system_prompt)
            
        # Get the formatted system prompt from the agent
        agent_system_prompt = self.agent_id.get_formatted_system_prompt()
        
        # Combine system prompts if both are provided
        combined_prompt = None
        if agent_system_prompt and system_prompt:
            combined_prompt = f"{agent_system_prompt}\n\n{system_prompt}"
        elif agent_system_prompt:
            combined_prompt = agent_system_prompt
        else:
            combined_prompt = system_prompt
            
        # Use the parent implementation with the combined system prompt
        return super().get_assistant_response(stream=stream, system_prompt=combined_prompt)
