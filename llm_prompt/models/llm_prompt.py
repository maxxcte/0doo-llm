import json
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LLMPrompt(models.Model):
    _name = "llm.prompt"
    _description = "LLM Prompt Template"
    _inherit = ["mail.thread"]
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
    category = fields.Selection(
        [
            ("analysis", "Analysis"),
            ("generation", "Content Generation"),
            ("code", "Code Related"),
            ("workflow", "Workflow"),
            ("conversion", "Format Conversion"),
            ("other", "Other"),
        ],
        default="other",
        required=True,
        tracking=True,
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
