from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LLMPrompt(models.Model):
    _name = "llm.prompt"
    _description = "LLM Prompt Template"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "name"

    name = fields.Char(
        string="Prompt Name",
        required=True,
        tracking=True,
        help="Unique identifier for the prompt template",
    )
    description = fields.Text(
        string="Description",
        tracking=True,
        help="Human-readable description of the prompt",
    )
    active = fields.Boolean(default=True)

    # Categorization
    category_id = fields.Many2one(
        "llm.prompt.category",
        string="Category",
        tracking=True,
        index=True,
        help="Category for organizing prompts",
    )

    # Tags
    tag_ids = fields.Many2many(
        'llm.prompt.tag',
        'llm_prompt_tag_rel',
        'prompt_id',
        'tag_id',
        string='Tags',
        help="Classify and analyze your prompts"
    )

    # Provider and Publisher relations
    provider_ids = fields.Many2many(
        'llm.provider',
        'llm_prompt_provider_rel',
        'prompt_id',
        'provider_id',
        string='Compatible Providers',
        help="LLM providers that can use this prompt",
    )

    publisher_ids = fields.Many2many(
        'llm.publisher',
        'llm_prompt_publisher_rel',
        'prompt_id',
        'publisher_id',
        string='Compatible Publishers',
        help="LLM publishers whose models work well with this prompt",
    )

    # Arguments
    argument_ids = fields.One2many(
        "llm.prompt.argument",
        "prompt_id",
        string="Arguments",
        help="Parameters that can be passed to this prompt",
    )
    argument_count = fields.Integer(
        compute="_compute_argument_count",
        string="Argument Count",
    )

    template_ids = fields.One2many(
        "llm.prompt.template",
        "prompt_id",
        string="Templates",
        help="Sequence of templates in a multi-step prompt",
    )
    template_count = fields.Integer(
        compute="_compute_template_count",
        string="Template Count",
    )

    # Resources
    resource_ids = fields.One2many(
        "llm.prompt.resource",
        "prompt_id",
        string="Resources",
        help="Additional context resources included with the prompt",
    )
    resource_count = fields.Integer(
        compute="_compute_resource_count",
        string="Resource Count",
    )

    # Example invocation
    example_args = fields.Text(
        string="Example Arguments",
        help="Example arguments in JSON format to test this prompt",
    )

    # Usage tracking
    usage_count = fields.Integer(
        string="Usage Count",
        default=0,
        readonly=True,
        help="Number of times this prompt has been used",
    )
    last_used = fields.Datetime(
        string="Last Used",
        readonly=True,
        help="When this prompt was last used",
    )

    _sql_constraints = [
        (
            "name_unique",
            "UNIQUE(name)",
            "The prompt name must be unique."
        ),
    ]

    @api.depends("argument_ids")
    def _compute_argument_count(self):
        for prompt in self:
            prompt.argument_count = len(prompt.argument_ids)

    @api.depends("template_ids")
    def _compute_template_count(self):
        for prompt in self:
            prompt.template_count = len(prompt.template_ids)

    @api.depends("resource_ids")
    def _compute_resource_count(self):
        for prompt in self:
            prompt.resource_count = len(prompt.resource_ids)

    def get_prompt_data(self):
        """Returns the prompt data in the MCP format"""
        self.ensure_one()

        return {
            "name": self.name,
            "description": self.description or "",
            "category": self.category_id.name if self.category_id else "",
            "arguments": [arg.get_argument_data() for arg in self.argument_ids],
        }

    def get_messages(self, arguments=None):
        """
        Generate messages for this prompt with the given arguments
        
        Args:
            arguments (dict): Dictionary of argument values
            
        Returns:
            list: List of messages for this prompt
        """
        self.ensure_one()
        arguments = arguments or {}

        messages = []

        # Add template messages
        for template in self.template_ids.sorted(key=lambda t: t.sequence):
            template_message = template.get_template_message(arguments)
            if template_message:
                messages.append(template_message)

                # Include resources if specified
                if template.include_resources and template.resource_ids:
                    for resource in template.resource_ids:
                        resource_message = resource.get_resource_message(arguments)
                        if resource_message:
                            messages.append(resource_message)

        # Update usage statistics
        self.usage_count += 1
        self.last_used = fields.Datetime.now()

        return messages
