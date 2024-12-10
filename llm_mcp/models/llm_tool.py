from odoo import api, fields, models
from odoo.exceptions import UserError


class LLMTool(models.Model):
    _inherit = "llm.tool"

    mcp_server_id = fields.Many2one(
        "llm.mcp.server", string="MCP Server", ondelete="cascade"
    )

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("mcp", "MCP Server")]

    def mcp_execute(self, **parameters):
        """Execute the tool on the MCP server"""
        self.ensure_one()

        if not self.mcp_server_id:
            raise UserError("This tool is not associated with an MCP server")

        if not self.mcp_server_id.is_active:
            raise UserError(f"MCP server '{self.mcp_server_id.name}' is not active")

        try:
            result = self.mcp_server_id.execute_tool(self.name, parameters)

            # Check for error in the result
            if result and isinstance(result, dict) and "error" in result:
                error_message = result["error"]
                raise UserError(f"Tool execution failed: {error_message}")

            return result
        except Exception as e:
            if not isinstance(e, UserError):
                raise UserError(
                    f"Error executing tool '{self.name}' on MCP server '{self.mcp_server_id.name}': {str(e)}"
                ) from e
            raise

    def execute(self, parameters):
        self.ensure_one()
        # if mcp tool, then we don't need to construct method signature to execute the tool
        # as it is handled by mcp server via mcp_execute
        if self.implementation == "mcp":
            result = self.mcp_execute(**parameters)
            return result
        else:
            return super().execute(parameters)
