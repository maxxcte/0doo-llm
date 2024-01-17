from odoo import api, models, fields

class LLMTool(models.Model):
    _inherit = "llm.tool"

    mcp_server_id = fields.Many2one(
        'llm.mcp.server',
        string="MCP Server",
        ondelete="cascade"
    )

    @api.model
    def _get_available_implementations(self):
        implementations = super()._get_available_implementations()
        return implementations + [("mcp", "MCP Server")]

    def mcp_execute(self, **parameters):
        """Execute the tool on the MCP server"""
        self.ensure_one()

        if not self.mcp_server_id:
            return {"error": "This tool is not associated with an MCP server"}

        return self.mcp_server_id.execute_tool(self.name, parameters)
