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
    
    def get_assistant_response(self, stream=True):
        """Override to include agent's system prompt if agent is set"""
        if self.agent_id and self.agent_id.system_prompt:
            # Get messages and format them with the provider
            messages = self.get_chat_messages()
            tool_ids = self.tool_ids.ids if self.tool_ids else None
            
            # Format messages using the provider (which will handle validation)
            try:
                formatted_messages = self.provider_id.format_messages(
                    messages, system_prompt=self.agent_id.system_prompt
                )
            except Exception:
                # Fall back to default formatting with system prompt
                formatted_messages = self._default_format_messages(
                    messages, system_prompt=self.agent_id.system_prompt
                )
            
            # Process response with possible tool calls
            response_generator = self._chat_with_tools(
                formatted_messages, tool_ids, stream
            )
            
            # Process the response stream
            content = ""
            assistant_tool_calls = []
            
            for response in response_generator:
                yield response
            
            return
        
        # If no agent or no system prompt, use the original method
        return super().get_assistant_response(stream=stream)
    
    def _default_format_messages(self, messages, system_prompt=None):
        """Override default message formatting to include system prompt if provided"""
        formatted_messages = []
        
        # Add system prompt if provided
        if system_prompt:
            formatted_messages.append(
                {
                    "role": "system",
                    "content": system_prompt,
                }
            )
        
        # Add the rest of the messages
        for message in messages:
            if message.author_id:
                # User message
                formatted_messages.append(
                    {
                        "role": "user",
                        "content": message.body,
                    }
                )
            else:
                # Assistant message
                formatted_messages.append(
                    {
                        "role": "assistant",
                        "content": message.body,
                    }
                )
        
        return formatted_messages
