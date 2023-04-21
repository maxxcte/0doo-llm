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
    )
    goal = fields.Text(
        string="Goal",
        help="The primary goal or objective of this agent",
        tracking=True,
    )
    background = fields.Text(
        string="Background",
        help="Background information for the agent to understand its context",
        tracking=True,
    )
    instructions = fields.Text(
        string="Instructions",
        help="Specific instructions for the agent to follow",
        tracking=True,
    )
    
    # Tools configuration
    tool_ids = fields.Many2many(
        "llm.tool",
        string="Preferred Tools",
        help="Tools that this agent can use",
        tracking=True,
    )
    
    # System prompt generation
    system_prompt = fields.Text(
        string="System Prompt",
        compute="_compute_system_prompt",
        store=True,
        readonly=False,
        help="The system prompt that will be sent to the LLM",
        tracking=True,
    )
    use_custom_system_prompt = fields.Boolean(
        string="Use Custom System Prompt",
        default=False,
        help="If enabled, the custom system prompt will be used instead of the generated one",
        tracking=True,
    )
    custom_system_prompt = fields.Text(
        string="Custom System Prompt",
        help="Custom system prompt to use when 'Use Custom System Prompt' is enabled",
        tracking=True,
    )
    
    # Thread count for reference
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
    
    @api.depends("role", "goal", "background", "instructions")
    def _compute_system_prompt(self):
        """Generate a system prompt based on the agent's configuration"""
        for record in self:
            if record.use_custom_system_prompt and record.custom_system_prompt:
                record.system_prompt = record.custom_system_prompt
            else:
                prompt_parts = []
                
                if record.role:
                    prompt_parts.append(f"You are a {record.role}.")
                
                if record.goal:
                    prompt_parts.append(f"Your goal is to {record.goal}")
                
                if record.background:
                    prompt_parts.append(f"Background: {record.background}")
                
                if record.instructions:
                    prompt_parts.append(f"Instructions: {record.instructions}")
                
                record.system_prompt = "\n\n".join(prompt_parts)
    
    def _compute_thread_count(self):
        """Compute the number of threads using this agent"""
        for record in self:
            record.thread_count = len(record.thread_ids)
    
    def action_view_threads(self):
        """Open the threads using this agent"""
        self.ensure_one()
        action = self.env["ir.actions.actions"]._for_xml_id("llm_thread.action_llm_thread")
        action["domain"] = [("agent_id", "=", self.id)]
        action["context"] = {"default_agent_id": self.id}
        return action
