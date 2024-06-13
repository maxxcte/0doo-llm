import json
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
        ondelete="restrict",
        tracking=True,
    )
    model_id = fields.Many2one(
        "llm.model",
        string="Model",
        domain="[('provider_id', '=', provider_id), ('model_use', 'in', ['chat', 'multimodal'])]",
        ondelete="restrict",
        tracking=True,
        required=False,
    )

    # Prompt template integration
    prompt_id = fields.Many2one(
        "llm.prompt",
        string="Prompt Template",
        ondelete="restrict",
        tracking=True,
        required=True,
        help="Prompt template to use for generating system prompts",
    )

    # Default values for prompt variables as JSON
    default_values = fields.Text(
        string="Default Values",
        help="JSON object with default values for prompt variables",
        default="{}",
        tracking=True,
    )

    # Tools configuration
    tool_ids = fields.Many2many(
        "llm.tool",
        string="Preferred Tools",
        help="Tools that this agent can use",
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

    system_prompt_preview = fields.Text(
        string="System Prompt Preview",
        compute="_compute_system_prompt_preview",
        help="Preview of the formatted system prompt based on the prompt template",
    )

    @api.depends('prompt_id', 'default_values')
    def _compute_system_prompt_preview(self):
        """Compute preview of the formatted system prompt"""
        for agent in self:
            agent.system_prompt_preview = agent.get_formatted_system_prompt()


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

    @api.model
    def create(self, vals):
        """Override create to ensure default_values is valid JSON"""
        if 'default_values' in vals and vals['default_values']:
            try:
                json.loads(vals['default_values'])
            except json.JSONDecodeError:
                vals['default_values'] = "{}"
        return super(LLMAgent, self).create(vals)

    @api.onchange('prompt_id')
    def _onchange_prompt_id(self):
        """Update default_values when prompt_id changes"""
        if self.prompt_id:
            # Get the prompt arguments schema
            try:
                args_schema = json.loads(self.prompt_id.arguments_json or "{}")
                default_values = {}

                # Extract default values from schema
                for arg_name, arg_schema in args_schema.items():
                    if "default" in arg_schema:
                        default_values[arg_name] = arg_schema["default"]

                # If we have any defaults, update default_values
                if default_values:
                    self.default_values = json.dumps(default_values, indent=2)
            except json.JSONDecodeError:
                pass

    def get_formatted_system_prompt(self):
        """Generate a formatted system prompt based on the prompt template"""
        self.ensure_one()

        if not self.prompt_id:
            return ""

        try:
            # Get the argument values from default_values
            arg_values = json.loads(self.default_values or "{}")

            # Get messages from the prompt template
            messages = self.prompt_id.get_messages(arg_values)

            # Find the system message
            system_message = next((msg for msg in messages if msg.get('role') == 'system'), None)
            if system_message and 'content' in system_message:
                if isinstance(system_message['content'], dict) and 'text' in system_message['content']:
                    return system_message['content']['text']
                elif isinstance(system_message['content'], str):
                    return system_message['content']

            # If no system message found, return the first message content
            if messages and 'content' in messages[0]:
                if isinstance(messages[0]['content'], dict) and 'text' in messages[0]['content']:
                    return messages[0]['content']['text']
                elif isinstance(messages[0]['content'], str):
                    return messages[0]['content']

        except Exception as e:
            _logger.error("Error generating system prompt from template: %s", str(e))

        return ""
