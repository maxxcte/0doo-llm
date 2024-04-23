from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LLMPromptArgument(models.Model):
    _name = "llm.prompt.argument"
    _description = "LLM Prompt Argument"
    _order = "name"

    name = fields.Char(
        string="Argument Name",
        required=True,
        help="Name of the argument (used in placeholders like {{name}})",
    )
    description = fields.Text(
        string="Description",
        help="Human-readable description of the argument",
    )
    required = fields.Boolean(
        string="Required",
        default=False,
        help="Whether this argument must be provided",
    )
    prompt_id = fields.Many2one(
        "llm.prompt",
        string="Prompt",
        required=True,
        ondelete="cascade",
    )
    
    # Argument type and validation
    argument_type = fields.Selection(
        [
            ("text", "Text"),
            ("number", "Number"),
            ("boolean", "Boolean"),
            ("selection", "Selection"),
            ("date", "Date"),
            ("resource", "Resource"),
        ],
        string="Argument Type",
        default="text",
        required=True,
    )
    selection_options = fields.Text(
        string="Selection Options",
        help="Comma-separated list of options for selection type",
    )
    default_value = fields.Text(
        string="Default Value",
        help="Default value for this argument if not provided",
    )
    
    # Validation fields
    min_length = fields.Integer(
        string="Minimum Length",
        help="Minimum length for text arguments",
    )
    max_length = fields.Integer(
        string="Maximum Length",
        help="Maximum length for text arguments",
    )
    min_value = fields.Float(
        string="Minimum Value",
        help="Minimum value for number arguments",
    )
    max_value = fields.Float(
        string="Maximum Value",
        help="Maximum value for number arguments",
    )
    
    _sql_constraints = [
        (
            "name_prompt_unique",
            "UNIQUE(name, prompt_id)",
            "Argument names must be unique per prompt"
        ),
    ]
    
    @api.constrains("name")
    def _check_name_format(self):
        for arg in self:
            if arg.name and not arg.name.replace("_", "").isalnum():
                raise ValidationError(_("Argument name must contain only letters, numbers, and underscores"))
    
    @api.constrains("argument_type", "selection_options")
    def _check_selection_options(self):
        for arg in self:
            if arg.argument_type == "selection" and not arg.selection_options:
                raise ValidationError(_("Selection options are required for selection type arguments"))
    
    @api.constrains("min_length", "max_length")
    def _check_length_constraints(self):
        for arg in self:
            if arg.min_length and arg.max_length and arg.min_length > arg.max_length:
                raise ValidationError(_("Minimum length cannot be greater than maximum length"))
    
    @api.constrains("min_value", "max_value")
    def _check_value_constraints(self):
        for arg in self:
            if arg.min_value and arg.max_value and arg.min_value > arg.max_value:
                raise ValidationError(_("Minimum value cannot be greater than maximum value"))
    
    def get_argument_data(self):
        """Returns the argument data in the MCP format"""
        self.ensure_one()
        
        return {
            "name": self.name,
            "description": self.description or "",
            "required": self.required,
        }
    
    def validate_value(self, value):
        """
        Validate the provided value against this argument's constraints
        
        Args:
            value: The value to validate
            
        Returns:
            tuple: (is_valid, error_message)
        """
        self.ensure_one()
        
        # Check required
        if self.required and (value is None or value == ""):
            return False, _("This argument is required")
        
        # If not required and no value provided, it's valid
        if not self.required and (value is None or value == ""):
            return True, ""
        
        # Type-specific validation
        if self.argument_type == "text":
            if self.min_length and len(str(value)) < self.min_length:
                return False, _("Text must be at least %s characters") % self.min_length
            if self.max_length and len(str(value)) > self.max_length:
                return False, _("Text must be at most %s characters") % self.max_length
                
        elif self.argument_type == "number":
            try:
                num_value = float(value)
                if self.min_value is not None and num_value < self.min_value:
                    return False, _("Value must be at least %s") % self.min_value
                if self.max_value is not None and num_value > self.max_value:
                    return False, _("Value must be at most %s") % self.max_value
            except (ValueError, TypeError):
                return False, _("Invalid number format")
                
        elif self.argument_type == "boolean":
            if not isinstance(value, bool) and str(value).lower() not in ["true", "false", "1", "0"]:
                return False, _("Value must be a boolean (true/false)")
                
        elif self.argument_type == "selection":
            options = [opt.strip() for opt in (self.selection_options or "").split(",")]
            if str(value) not in options:
                return False, _("Value must be one of: %s") % ", ".join(options)
                
        elif self.argument_type == "date":
            try:
                fields.Date.from_string(value)
            except ValueError:
                return False, _("Invalid date format (use YYYY-MM-DD)")
        
        return True, ""
