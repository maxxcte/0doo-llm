import logging

from odoo import api, models

_logger = logging.getLogger(__name__)


class MCPBusHandler(models.AbstractModel):
    """
    Bus message handler for MCP server communication
    This model processes bus messages received from MCP servers
    """

    _name = "llm.mcp.bus.handler"
    _description = "MCP Bus Message Handler"

    @api.model
    def _register_hook(self):
        """Register hook to initialize bus listener on server start"""
        super()._register_hook()

        # This will be called automatically when the registry is built
        self._start_bus_listeners()
        return True

    @api.model
    def _start_bus_listeners(self):
        """Start listening for MCP bus messages"""
        _logger.info("Starting MCP bus message listeners...")

        # First, find all active MCP servers
        servers = self.env["llm.mcp.server"].search([("is_active", "=", True)])

        for server in servers:
            if server.transport == "stdio" and server.is_connected:
                try:
                    _logger.info(f"Restarting MCP server {server.name} ({server.id})")
                    # This will initialize the bus manager for the server
                    server.start_server()
                    _logger.info(f"MCP server {server.name} successfully restarted")
                except Exception as e:
                    _logger.error(f"Failed to restart MCP server {server.name}: {e}")

    @api.model
    def handle_mcp_message(self, server_id, message_type, message_data):
        """
        Handle a message from an MCP server

        :param server_id: ID of the MCP server
        :param message_type: Type of the message (request, response, notification)
        :param message_data: The actual message content
        """
        try:
            if message_type == "response":
                # Forward the response to the appropriate listener
                self.env["bus.bus"]._sendone(
                    f"mcp_response_{server_id}",
                    "mcp.response",
                    {"server_id": server_id, "response": message_data},
                )
            elif message_type == "notification":
                # Handle notifications from the MCP server
                # Notifications don't need responses and can be processed directly
                self._process_mcp_notification(server_id, message_data)
            else:
                _logger.warning(
                    f"Received unknown message type from MCP server {server_id}: {message_type}"
                )

        except Exception as e:
            _logger.exception(
                f"Error handling MCP message from server {server_id}: {e}"
            )

    def _process_mcp_notification(self, server_id, notification):
        """Process a notification from an MCP server"""
        if not isinstance(notification, dict) or "method" not in notification:
            _logger.warning(
                f"Received invalid notification format from server {server_id}"
            )
            return

        method = notification.get("method")
        params = notification.get("params", {})

        _logger.info(f"Processing MCP notification: {method} from server {server_id}")

        # Handle different types of notifications
        if method == "notifications/toolStateChanged":
            # Tool state has changed, refresh tools
            self._handle_tool_state_changed(server_id, params)
        elif method == "notifications/serverStateChanged":
            # Server state has changed
            self._handle_server_state_changed(server_id, params)
        else:
            _logger.info(f"Unhandled MCP notification method: {method}")

    def _handle_tool_state_changed(self, server_id, params):
        """Handle tool state change notification"""
        try:
            server = self.env["llm.mcp.server"].browse(server_id)
            if not server.exists():
                return

            # Refresh tools list
            server.list_tools()
            _logger.info(f"Refreshed tools for server {server.name} after state change")
        except Exception as e:
            _logger.error(
                f"Error handling tool state change for server {server_id}: {e}"
            )

    def _handle_server_state_changed(self, server_id, params):
        """Handle server state change notification"""
        try:
            server = self.env["llm.mcp.server"].browse(server_id)
            if not server.exists():
                return

            new_state = params.get("state")
            if new_state == "disconnected":
                # Server reports it's disconnected
                server.is_connected = False
                _logger.warning(f"MCP server {server.name} reported disconnected state")
            elif new_state == "connected":
                # Server reports it's connected
                server.is_connected = True
                _logger.info(f"MCP server {server.name} reported connected state")
        except Exception as e:
            _logger.error(
                f"Error handling server state change for server {server_id}: {e}"
            )
