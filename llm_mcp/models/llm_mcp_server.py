import json
import logging

from odoo import api, fields, models
from odoo.exceptions import UserError, ValidationError

from .llm_mcp_bus_manager import MCPBusManager

_logger = logging.getLogger(__name__)


class LLMMCPServer(models.Model):
    _name = "llm.mcp.server"
    _description = "LLM MCP Server"
    _inherit = ["mail.thread"]

    name = fields.Char(required=True, tracking=True)
    transport = fields.Selection(
        [("internal", "Internal"), ("stdio", "Standard IO")],
        string="Transport Type",
        default="stdio",
        required=True,
        tracking=True,
    )

    command = fields.Char(
        string="Command",
        help="Command to execute when transport is stdio",
        tracking=True,
    )
    args = fields.Char(
        string="Arguments", help="Command line arguments for the command", tracking=True
    )

    tool_ids = fields.One2many("llm.tool", "mcp_server_id", string="MCP Tools")

    is_connected = fields.Boolean(string="Connected", default=False, tracking=True)
    is_active = fields.Boolean(string="Active", default=True, tracking=True)

    protocol_version = fields.Char(string="Protocol Version", readonly=True)
    server_info = fields.Char(string="Server Info", readonly=True)

    @api.constrains("transport", "command")
    def _check_command(self):
        for server in self:
            if server.transport == "stdio" and not server.command:
                raise ValidationError("Command is required for Standard IO transport")

    def _get_manager(self):
        """Get a manager instance for this server"""
        if self.transport != "stdio":
            return None

        try:
            manager = MCPBusManager(self.env, self.id, self.command, self.args)
            return manager
        except Exception as e:
            error_msg = f"Failed to get manager for server {self.name}: {str(e)}"
            _logger.error(error_msg)
            raise UserError(error_msg) from e

    def start_server(self):
        """Start the server and connect to it"""
        self.ensure_one()
        if self.is_connected:
            return True

        if self.transport == "stdio":
            try:
                manager = self._get_manager()
                if not manager:
                    raise UserError(f"Failed to create manager for server {self.name}")

                # Make sure the process starts
                if not manager._start_process():
                    raise UserError(f"Failed to start process for server {self.name}")

                # Ensure MCP is initialized
                if not manager._initialized:
                    if not manager._initialize_mcp():
                        raise UserError(
                            f"Failed to initialize MCP protocol for server {self.name}"
                        )

                # Test connection by asking for tools
                tools = manager.list_tools()
                if tools is None:
                    raise UserError(f"Failed to retrieve tools from server {self.name}")

                self.is_connected = True
                self._update_tools(tools)

                # Update protocol information
                if hasattr(manager, "protocol_version"):
                    self.protocol_version = manager.protocol_version
                if hasattr(manager, "server_info"):
                    self.server_info = json.dumps(manager.server_info or {})

                return True
            except Exception as e:
                error_msg = f"Failed to start MCP server {self.name}: {str(e)}"
                _logger.error(error_msg)
                raise UserError(error_msg) from e
        elif self.transport == "internal":
            # For internal transport, no process to start
            self.is_connected = True
            return True

    def stop_server(self):
        """Stop the server and disconnect from it"""
        self.ensure_one()
        if not self.is_connected:
            return True

        if self.transport == "stdio":
            try:
                manager = self._get_manager()
                if manager:
                    manager.close()
            except Exception as e:
                error_msg = f"Error stopping MCP server {self.name}: {str(e)}"
                _logger.error(error_msg)
                # We don't raise an error here as we want to ensure is_connected is set to False

        self.is_connected = False
        return True

    def list_tools(self):
        """Fetch and update tools from the MCP server"""
        self.ensure_one()

        if not self.is_connected:
            try:
                if not self.start_server():
                    raise UserError(f"Could not connect to MCP server {self.name}")
            except Exception as e:
                raise UserError(
                    f"Could not connect to MCP server {self.name}: {str(e)}"
                ) from e

        if self.transport == "stdio":
            try:
                manager = self._get_manager()
                if not manager:
                    raise UserError(f"Could not connect to MCP server {self.name}")

                tools = manager.list_tools()
                if tools is None:
                    raise UserError(
                        f"Failed to fetch tools from MCP server {self.name}"
                    )

                self._update_tools(tools)
                return self.tool_ids
            except Exception as e:
                error_msg = f"Error listing tools from server {self.name}: {str(e)}"
                _logger.error(error_msg)
                raise UserError(error_msg) from e
        elif self.transport == "internal":
            # For internal, just return the tools already defined
            return self.tool_ids

    def _update_tools(self, tools_data):
        """Update or create tools based on the data from the MCP server"""
        Tool = self.env["llm.tool"]

        # Track existing tools to handle deletions
        existing_tools = {tool.name: tool for tool in self.tool_ids}
        updated_tools = []

        for tool_data in tools_data:
            tool_name = tool_data.get("name")
            if not tool_name:
                continue

            tool = existing_tools.get(tool_name)

            # Extract input schema
            input_schema = tool_data.get("inputSchema", {})

            tool_values = {
                "name": tool_name,
                "description": tool_data.get("description", ""),
                "implementation": "mcp",
                "mcp_server_id": self.id,
                "input_schema": json.dumps(input_schema),
            }

            # Add any annotations if present
            annotations = tool_data.get("annotations", {})
            if annotations:
                if "title" in annotations:
                    tool_values["title"] = annotations["title"]
                if "readOnlyHint" in annotations:
                    tool_values["read_only_hint"] = annotations["readOnlyHint"]
                if "idempotentHint" in annotations:
                    tool_values["idempotent_hint"] = annotations["idempotentHint"]
                if "destructiveHint" in annotations:
                    tool_values["destructive_hint"] = annotations["destructiveHint"]
                if "openWorldHint" in annotations:
                    tool_values["open_world_hint"] = annotations["openWorldHint"]

            if tool:
                # Update existing tool
                tool.write(tool_values)
                updated_tools.append(tool.id)
            else:
                # Create new tool
                tool = Tool.create(tool_values)
                updated_tools.append(tool.id)

        # Handle tool deletion (tools that existed but weren't in the update)
        tools_to_delete = [
            tool
            for name, tool in existing_tools.items()
            if tool.id not in updated_tools
        ]
        if tools_to_delete:
            tools_to_delete_ids = [t.id for t in tools_to_delete]
            Tool.browse(tools_to_delete_ids).unlink()

        return True

    def execute_tool(self, tool_name, parameters):
        """Execute a tool on the MCP server"""
        self.ensure_one()

        if not self.is_connected:
            try:
                if not self.start_server():
                    raise UserError(f"Could not connect to MCP server {self.name}")
            except Exception as e:
                raise UserError(
                    f"Could not connect to MCP server {self.name}: {str(e)}"
                ) from e

        if self.transport == "stdio":
            try:
                manager = self._get_manager()
                if not manager:
                    raise UserError(f"Could not connect to MCP server {self.name}")

                result = manager.call_tool(tool_name, parameters)
                if result is None:
                    raise UserError(
                        f"Failed to execute tool {tool_name} on server {self.name}"
                    )
                return result
            except Exception as e:
                error_msg = f"Error executing tool {tool_name} on MCP server: {str(e)}"
                _logger.error(error_msg)
                return {"error": str(e)}
        elif self.transport == "internal":
            # For internal transport, we don't have a real execute mechanism
            return {"error": "Execution not implemented for internal transport"}
