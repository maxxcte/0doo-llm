from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LLMPromptTemplate(models.Model):
    _name = "llm.prompt.template"
    _description = "LLM Prompt Template"
    _order = "sequence, id"

    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in which templates are processed",
    )
    prompt_id = fields.Many2one(
        "llm.prompt",
        string="Prompt",
        required=True,
        ondelete="cascade",
    )

    # Template role
    role = fields.Selection(
        [
            ("user", "User"),
            ("assistant", "Assistant"),
            ("system", "System"),
        ],
        string="Role",
        default="user",
        required=True,
        help="Role of this template in the conversation",
    )

    # Content
    content = fields.Text(
        string="Content",
        required=True,
        help="Content of this template with placeholders for arguments (use {{argument_name}})",
    )

    # Conditional execution
    condition = fields.Char(
        string="Execution Condition",
        help="Python expression determining whether to include this template (e.g., 'debug' in arguments)",
    )

    # Computed field to show used arguments
    used_arguments = fields.Char(
        string="Used Arguments",
        compute="_compute_used_arguments",
        help="Arguments used in this template",
    )

    @api.depends('content')
    def _compute_used_arguments(self):
        """Compute arguments used in this template"""
        for template in self:
            if not template.content:
                template.used_arguments = ""
                continue

            args = template.prompt_id._extract_arguments_from_template(template.content)
            template.used_arguments = ", ".join(sorted(args)) if args else ""

    def get_template_message(self, arguments=None):
        """
        Generate a message for this template with the given arguments

        Args:
            arguments (dict): Dictionary of argument values

        Returns:
            dict: Message dictionary for this template
        """
        self.ensure_one()
        arguments = arguments or {}

        # Check execution condition
        if self.condition:
            try:
                if not self._evaluate_condition(self.condition, arguments):
                    return None
            except Exception as e:
                # Log but don't fail if condition evaluation fails
                self.prompt_id.message_post(
                    body=_("Error evaluating condition for template %s: %s") % (self.id, str(e))
                )
                return None

        # Replace argument placeholders in content
        content = self.content
        for arg_name, arg_value in arguments.items():
            placeholder = "{{" + arg_name + "}}"
            placeholderWithSpace = "{{ " + arg_name + " }}"
            # maybe can be done via regex, kept it simple for now
            if placeholder in content:
                content = content.replace(placeholder, str(arg_value))
            elif placeholderWithSpace in content:
                content = content.replace(placeholderWithSpace, str(arg_value))

        # Create the message
        return {
            "role": self.role,
            "content": {
                "type": "text",
                "text": content,
            },
        }

    def _evaluate_condition(self, condition, arguments):
        """Evaluate the execution condition"""
        # Create a safe evaluation context with just the arguments
        eval_context = {"arguments": arguments}
        # Add common operators
        for k in arguments:
            eval_context[k] = arguments[k]

        # Evaluate the condition expression
        return eval(condition, {"__builtins__": {}}, eval_context)
