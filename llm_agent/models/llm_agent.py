import logging

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LLMAgent(models.Model):
    _name = "llm.agent"
    _description = "LLM Agent"
    _inherit = ["mail.thread"]
    _order = "name"

    name = fields.Char(
        string="Name",
        required=True,
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)

    # Agent configuration
    provider_id = fields.Many2one(
        "llm.provider",
        string="Provider",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    model_id = fields.Many2one(
        "llm.model",
        string="Model",
        required=True,
        domain="[('provider_id', '=', provider_id), ('model_use', 'in', ['chat', 'multimodal'])]",
        ondelete="restrict",
        tracking=True,
    )

    # Agent capabilities
    role = fields.Char(
        string="Role",
        help="The role of the agent (e.g., 'Assistant', 'Customer Support', 'Data Analyst')",
        tracking=True,
        required=True,
    )
    goal = fields.Text(
        string="Goal",
        help="The primary goal or objective of this agent",
        tracking=True,
        required=True,
    )
    background = fields.Text(
        string="Background",
        help="Background information for the agent to understand its context",
        tracking=True,
        required=True,
    )
    instructions = fields.Text(
        string="Instructions",
        help="Specific instructions for the agent to follow",
        tracking=True,
        required=True,
    )

    # Tools configuration
    tool_ids = fields.Many2many(
        "llm.tool",
        string="Preferred Tools",
        help="Tools that this agent can use",
        tracking=True,
    )

    # System prompt template
    system_prompt = fields.Text(
        string="System Prompt Template",
        default="""You are a {{ role }}.

Your goal is to {{ goal }}

Background: {{ background }}

Instructions: {{ instructions }}""",
        help="Template for the system prompt. Use {{ field_name }} placeholders for variable substitution.",
        tracking=True,
    )

    # Stats
    thread_count = fields.Integer(
        string="Thread Count",
        compute="_compute_thread_count",
        help="Number of threads using this agent",
    )
    thread_ids = fields.One2many(
        "llm.thread",
        "agent_id",
        string="Threads",
        help="Threads using this agent",
    )

    @api.depends("thread_ids")
    def _compute_thread_count(self):
        """Compute the number of threads using this agent"""
        for agent in self:
            agent.thread_count = len(agent.thread_ids)

    def action_view_threads(self):
        """Open the threads using this agent"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id(
            "llm_thread.llm_thread_action"
        )
        action["domain"] = [("agent_id", "=", self.id)]
        action["context"] = {"default_agent_id": self.id}
        return action

    def get_formatted_system_prompt(self):
        """Generate a formatted system prompt based on the template and agent's configuration"""
        self.ensure_one()
        if not self.system_prompt:
            return ""

        # Create a dictionary with the field values for template substitution
        values = {
            "role": self.role,
            "goal": self.goal,
            "background": self.background,
            "instructions": self.instructions,
        }

        # Replace template variables with actual values
        prompt = self.system_prompt
        for key, value in values.items():
            placeholder = "{{ " + key + " }}"
            prompt = prompt.replace(placeholder, value)

        return prompt
