from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class LLMPromptResource(models.Model):
    _name = "llm.prompt.resource"
    _description = "LLM Prompt Resource"
    _order = "sequence, id"

    name = fields.Char(
        string="Resource Name",
        required=True,
        help="Name of this resource context",
    )
    sequence = fields.Integer(
        string="Sequence",
        default=10,
        help="Order in which resources are included",
    )
    prompt_id = fields.Many2one(
        "llm.prompt",
        string="Prompt",
        required=True,
        ondelete="cascade",
    )
    
    # Resource type and content
    resource_type = fields.Selection(
        [
            ("text", "Text Content"),
            ("file", "File Content"),
            ("url", "URL Content"),
            ("database", "Database Query"),
            ("code", "Code Snippet"),
            ("dynamic", "Dynamic Content"),
        ],
        string="Resource Type",
        default="text",
        required=True,
    )
    
    mime_type = fields.Char(
        string="MIME Type",
        help="The MIME type of the resource content",
        default="text/plain",
    )
    
    # Content fields
    content = fields.Text(
        string="Content",
        help="Text content to include as context",
    )
    file_data = fields.Binary(
        string="File Data",
        attachment=True,
        help="Binary file content to include",
    )
    file_name = fields.Char(
        string="File Name",
    )
    url = fields.Char(
        string="URL",
        help="URL to fetch content from",
    )
    database_query = fields.Text(
        string="Database Query",
        help="SQL query or ORM expression to get content",
    )
    
    # Role information
    resource_role = fields.Selection(
        [
            ("user", "User"),
            ("assistant", "Assistant"),
            ("system", "System"),
        ],
        string="Message Role",
        default="user",
        required=True,
        help="Role of this resource in the conversation",
    )
    
    # Dynamic content controls
    is_dynamic = fields.Boolean(
        string="Dynamic Content",
        default=False,
        help="Whether this resource includes dynamic content based on arguments",
    )
    dynamic_uri_template = fields.Char(
        string="URI Template",
        help="Template for resource URI with placeholders (e.g., logs://recent?timeframe={{timeframe}})",
    )

    # Conditional inclusion
    condition = fields.Char(
        string="Inclusion Condition",
        help="Python expression determining whether to include this resource (e.g., 'debug' in arguments)",
    )
    
    @api.constrains("resource_type", "content", "file_data", "url", "database_query")
    def _check_resource_content(self):
        for resource in self:
            if resource.resource_type == "text" and not resource.content:
                raise ValidationError(_("Content is required for text resources"))
            elif resource.resource_type == "file" and not resource.file_data:
                raise ValidationError(_("File data is required for file resources"))
            elif resource.resource_type == "url" and not resource.url:
                raise ValidationError(_("URL is required for URL resources"))
            elif resource.resource_type == "database" and not resource.database_query:
                raise ValidationError(_("Database query is required for database resources"))
            elif resource.resource_type == "code" and not resource.content:
                raise ValidationError(_("Content is required for code snippet resources"))

    def get_resource_message(self, arguments=None):
        """
        Generate a resource message with the given arguments
        
        Args:
            arguments (dict): Dictionary of argument values
            
        Returns:
            dict: Message dictionary with resource
        """
        self.ensure_one()
        arguments = arguments or {}
        
        # Check inclusion condition
        if self.condition:
            try:
                if not self._evaluate_condition(self.condition, arguments):
                    return None
            except Exception as e:
                # Log but don't fail if condition evaluation fails
                self.prompt_id.message_post(
                    body=_("Error evaluating condition for resource %s: %s") % (self.name, str(e))
                )
                return None
        
        # Get resource content
        resource_content = self._get_resource_content(arguments)
        if not resource_content:
            return None
            
        # Build resource URI
        uri = self._get_resource_uri(arguments)
        
        # Create the message with resource content
        return {
            "role": self.resource_role,
            "content": {
                "type": "resource",
                "resource": {
                    "uri": uri,
                    "text": resource_content,
                    "mimeType": self.mime_type or "text/plain",
                },
            },
        }
    
    def _get_resource_content(self, arguments):
        """Get the content for this resource based on type"""
        if self.resource_type == "text" or self.resource_type == "code":
            content = self.content
            # Replace argument placeholders
            for arg_name, arg_value in arguments.items():
                content = content.replace("{{" + arg_name + "}}", str(arg_value))
            return content
            
        elif self.resource_type == "file":
            # Return file content (implement file reading logic)
            return "File content placeholder"  # TODO: Implement actual file content reading
            
        elif self.resource_type == "url":
            # Fetch URL content (implement URL fetching logic)
            return "URL content placeholder"  # TODO: Implement actual URL fetching
            
        elif self.resource_type == "database":
            # Run database query (implement query execution logic)
            return "Database content placeholder"  # TODO: Implement actual query execution
            
        elif self.resource_type == "dynamic":
            # Handle dynamic content generation
            return "Dynamic content placeholder"  # TODO: Implement dynamic content generation
            
        return ""
    
    def _get_resource_uri(self, arguments):
        """Generate the URI for this resource"""
        if self.is_dynamic and self.dynamic_uri_template:
            uri = self.dynamic_uri_template
            # Replace argument placeholders
            for arg_name, arg_value in arguments.items():
                uri = uri.replace("{{" + arg_name + "}}", str(arg_value))
            return uri
        
        # Default URIs based on resource type
        if self.resource_type == "file" and self.file_name:
            return f"file:///{self.file_name}"
        elif self.resource_type == "url":
            return self.url
        elif self.resource_type == "database":
            return "database://query"
        
        # Fallback to a generic resource identifier
        return f"resource://{self.prompt_id.name}/{self.name}"
    
    def _evaluate_condition(self, condition, arguments):
        """Evaluate the inclusion condition"""
        # Create a safe evaluation context with just the arguments
        eval_context = {"arguments": arguments}
        # Add common operators
        for k in arguments:
            eval_context[k] = arguments[k]
        
        # Evaluate the condition expression
        return eval(condition, {"__builtins__": {}}, eval_context)
