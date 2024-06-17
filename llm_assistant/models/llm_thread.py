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
        return self.write(
            {
                "agent_id": agent_id,
                "provider_id": agent.provider_id.id if agent.provider_id else False,
                "model_id": agent.model_id.id if agent.model_id else False,
                "tool_ids": [(6, 0, agent.tool_ids.ids)],
            }
        )

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
            return super().get_assistant_response(
                stream=stream, system_prompt=system_prompt
            )

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
        return super().get_assistant_response(
            stream=stream, system_prompt=combined_prompt
        )
