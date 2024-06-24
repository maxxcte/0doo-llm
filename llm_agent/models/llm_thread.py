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

    def set_agent(self, agent_id):
        """Set the agent for this thread and update related fields

        Args:
            agent_id (int): The ID of the agent to set

        Returns:
            bool: True if successful, False otherwise
        """
        self.ensure_one()

        # If agent_id is False or 0, just clear the agent
        if not agent_id:
            return self.write({"agent_id": False})

        # Get the agent record
        agent = self.env["llm.agent"].browse(agent_id)
        if not agent.exists():
            return False

        # Update the thread with the agent and related fields
        update_vals = {
            "agent_id": agent_id,
            "tool_ids": [(6, 0, agent.tool_ids.ids)],
        }
        if agent.provider_id.id:
            update_vals["provider_id"] = agent.provider_id.id
        if agent.model_id.id:
            update_vals["model_id"] = agent.model_id.id
        return self.write(update_vals)

    def action_open_thread(self):
        """Open the thread in the chat client interface

        Returns:
            dict: Action to open the thread in the chat client
        """
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "llm_thread.chat_client_action",
            "params": {
                "default_active_id": self.id,
            },
            "context": {
                "active_id": self.id,
            },
            "target": "current",
        }
    # override to include agent's system prompt
    def _get_system_prompt(self):
        """Hook: return a system prompt for chat. Override in other modules. If needed"""
        self.ensure_one()
        system_prompt = super()._get_system_prompt()
        
        if self.agent_id:
            assistant_system_prompt = self.agent_id.get_formatted_system_prompt()
        
        if assistant_system_prompt and system_prompt:
            system_prompt = f"{assistant_system_prompt}\n\n{system_prompt}"
        elif assistant_system_prompt:
            system_prompt = assistant_system_prompt
        
        return system_prompt