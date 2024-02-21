import logging
import json
import threading
import time
import uuid
from contextlib import contextmanager

from odoo import api, models, fields
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

class MCPBusManager:
    """
    Manager for MCP server communication using the Odoo bus system.
    This replaces the direct pipe communication with a bus-based approach.
    """
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, env, server_id, command=None, args=None):
        """Singleton pattern to ensure only one instance exists per server"""
        key = f"server_{server_id}"

        with cls._lock:
            if key not in cls._instances:
                instance = super(MCPBusManager, cls).__new__(cls)
                instance._init_properties(env, server_id, command, args)
                cls._instances[key] = instance
            return cls._instances[key]

    def _init_properties(self, env, server_id, command, args):
        """Initialize instance properties"""
        self.env = env
        self.server_id = server_id
        self.command = command
        self.args = args
        self._initialized = False
        self._request_counter = 0
        self._pending_requests = {}
        self.protocol_version = None
        self.server_info = None

        # Generate unique channel names for this MCP server
        self.mcp_channel = f"mcp_server_{server_id}"
        self.response_channel = f"mcp_response_{server_id}"

        # Event for waiting for responses
        self._response_event = threading.Event()
        self._responses = {}

        # Flag to track if bridge is running
        self._bridge_started = False

    def start_bridge(self):
        """Start the bus bridge to the MCP server process"""
        if self._bridge_started:
            _logger.info(f"Bridge for MCP server {self.server_id} is already running")
            return True

        try:
            # Construct the command for the bridge
            full_command = self.command
            if self.args:
                full_command = f"{full_command} {self.args}"

            # Start the bridge using our integrated bus bridge
            result = self.env['llm.mcp.bus.bridge'].start_bridge(
                command=full_command,
                channels_to_subscribe=[
                    self.mcp_channel,      # Channel for sending commands to MCP server
                    self.response_channel,  # Channel for receiving responses
                ],
                channel_prefixes_to_forward=['mcp.'],  # Only forward MCP-related messages
                server_id=self.server_id
            )

            if result:
                _logger.info(f"Started bus bridge for MCP server {self.server_id}")
                self._bridge_started = True

                # Subscribe to the response channel to receive messages
                self._subscribe_to_responses()

                return True
            else:
                _logger.error(f"Failed to start bus bridge for MCP server {self.server_id}")
                return False

        except Exception as e:
            _logger.error(f"Error starting bus bridge for MCP server {self.server_id}: {str(e)}")
            return False

    def stop_bridge(self):
        """Stop the bus bridge to the MCP server process"""
        if not self._bridge_started:
            return True

        try:
            # Stop the bridge
            result = self.env['llm.mcp.bus.bridge'].stop_bridge(server_id=self.server_id)
            if result:
                _logger.info(f"Stopped bus bridge for MCP server {self.server_id}")
                self._bridge_started = False
                return True
            else:
                _logger.warning(f"Failed to stop bus bridge for MCP server {self.server_id}")
                return False
        except Exception as e:
            _logger.error(f"Error stopping bus bridge for MCP server {self.server_id}: {str(e)}")
            return False

    def _subscribe_to_responses(self):
        """Subscribe to the response channel to receive MCP responses"""
        # This is handled by the simple.bus.bridge, but we may need to add
        # additional subscribers or handlers here in the future
        pass

    def _get_next_request_id(self):
        """Get a unique request ID for JSON-RPC requests"""
        with self._lock:
            self._request_counter += 1
            return self._request_counter

    def _send_message(self, message):
        """Send a message to the MCP server via the bus"""
        try:
            # Add timestamp and ensure we have an ID
            if 'id' not in message:
                message['id'] = self._get_next_request_id()

            # Register this request ID for waiting
            request_id = message['id']
            self._pending_requests[request_id] = {
                'timestamp': time.time(),
                'message': message,
                'response': None
            }

            # Clear response event
            self._response_event.clear()

            # Send the message via bus
            self.env['bus.bus']._sendone(
                self.mcp_channel,
                'mcp.request',
                message
            )

            _logger.debug(f"Sent MCP message: {json.dumps(message)}")
            return request_id

        except Exception as e:
            _logger.error(f"Error sending message to MCP server: {str(e)}")
            raise UserError(f"Failed to communicate with MCP server: {str(e)}")

    def _wait_for_response(self, request_id, timeout=10):
        """Wait for a response from the MCP server"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if we have a response
            if request_id in self._responses:
                response = self._responses.pop(request_id)
                if request_id in self._pending_requests:
                    del self._pending_requests[request_id]
                return response

            # Wait for the event with timeout
            self._response_event.wait(0.5)

        # Timeout reached
        _logger.error(f"Timeout waiting for response to request {request_id}")

        # Clean up
        if request_id in self._pending_requests:
            del self._pending_requests[request_id]

        return None

    def _handle_response(self, response):
        """Handle a response from the MCP server"""
        if not isinstance(response, dict) or 'id' not in response:
            _logger.warning(f"Received invalid response format: {response}")
            return

        request_id = response['id']

        # Store the response
        self._responses[request_id] = response

        # Notify waiting threads
        self._response_event.set()

    def _initialize_mcp(self):
        """Initialize the MCP protocol with the server"""
        if self._initialized:
            _logger.info("MCP protocol already initialized")
            return True

        try:
            # Send initialize request according to MCP protocol
            initialize_request = {
                "jsonrpc": "2.0",
                "id": self._get_next_request_id(),
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": "odoo-llm-mcp-bus",
                        "version": "1.0.0"
                    },
                    "protocolVersion": "0.1.0",
                    "capabilities": {
                        "tools": {}
                    }
                }
            }

            request_id = initialize_request["id"]
            _logger.info(f"Initializing MCP protocol with request id {request_id}")

            # Send the request
            self._send_message(initialize_request)

            # Wait for response
            response = self._wait_for_response(request_id)

            if response is None:
                _logger.error(f"No response received for MCP initialization")
                return False

            if "result" in response:
                self._initialized = True

                # Store protocol information
                if "protocolVersion" in response["result"]:
                    self.protocol_version = response["result"]["protocolVersion"]
                if "serverInfo" in response["result"]:
                    self.server_info = response["result"]["serverInfo"]

                # Send initialized notification
                initialized_notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {}
                }
                _logger.info(f"Sending initialized notification")
                self._send_message(initialized_notification)

                _logger.info(f"MCP server initialized successfully with protocol version {self.protocol_version}")
                return True
            else:
                error_message = "Unknown error"
                if "error" in response:
                    error_message = response["error"].get("message", "Unknown error")
                _logger.error(f"Failed to initialize MCP server: {error_message}")
                return False

        except Exception as e:
            _logger.error(f"Error initializing MCP server: {str(e)}")
            return False

    def list_tools(self):
        """Send a tools/list request to the server"""
        # Ensure MCP is initialized
        if not self._initialized and not self._initialize_mcp():
            _logger.error("Failed to initialize MCP before listing tools")
            return None

        try:
            request_id = self._get_next_request_id()
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/list",
                "params": {}
            }

            _logger.info(f"Sending tools/list request with id {request_id}")
            self._send_message(request)

            # Wait for response
            response = self._wait_for_response(request_id)

            if response is None:
                _logger.error("No response received for tools/list request")
                return None

            if "result" in response and "tools" in response["result"]:
                _logger.info(f"Successfully listed {len(response['result']['tools'])} tools from MCP server")
                return response["result"]["tools"]
            else:
                error_message = "Unknown error"
                if "error" in response:
                    error_message = response["error"].get("message", "Unknown error")
                _logger.error(f"Error listing tools: {error_message}")
                return None

        except Exception as e:
            _logger.error(f"Exception listing tools: {str(e)}")
            return None

    def call_tool(self, tool_name, arguments):
        """Call a tool on the server"""
        # Ensure MCP is initialized
        if not self._initialized and not self._initialize_mcp():
            _logger.error(f"Failed to initialize MCP before calling tool {tool_name}")
            return {"error": "Failed to initialize MCP connection"}

        try:
            request_id = self._get_next_request_id()
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": arguments
                }
            }

            _logger.info(f"Sending tools/call request for tool '{tool_name}' with id {request_id}")
            self._send_message(request)

            # Wait for response
            response = self._wait_for_response(request_id, timeout=30)  # Longer timeout for tool execution

            if response is None:
                _logger.error(f"No response received for tools/call request for tool '{tool_name}'")
                return {"error": "No response from MCP server"}

            if "result" in response:
                # Handle tool call result according to MCP protocol
                result = response["result"]
                if "isError" in result and result["isError"]:
                    # Tool execution failed
                    error_content = ""
                    if "content" in result:
                        for content_item in result["content"]:
                            if content_item.get("type") == "text":
                                error_content += content_item.get("text", "")
                    _logger.error(f"Tool '{tool_name}' execution failed: {error_content}")
                    return {"error": error_content or "Tool execution failed"}

                # Tool execution succeeded, extract content
                content_result = {}
                if "content" in result:
                    for content_item in result["content"]:
                        if content_item.get("type") == "text":
                            # If it's JSON, try to parse it
                            try:
                                text_content = content_item.get("text", "")
                                content_result = json.loads(text_content)
                            except json.JSONDecodeError:
                                # If not JSON, return as plain text
                                content_result = {"result": text_content}
                _logger.info(f"Tool '{tool_name}' execution succeeded")
                return content_result
            else:
                error_message = "Unknown error"
                if "error" in response:
                    error_message = response["error"].get("message", "Unknown error")
                _logger.error(f"Error calling tool {tool_name}: {error_message}")
                return {"error": error_message}

        except Exception as e:
            _logger.error(f"Exception calling tool {tool_name}: {str(e)}")
            return {"error": str(e)}


class MCPBusListener(models.AbstractModel):
    """
    Model to handle MCP bus messages at the Odoo level.
    This acts as a bridge between the bus system and the MCPBusManager instances.
    """
    _name = 'llm.mcp.bus.listener'
    _description = 'LLM MCP Bus Message Listener'

    @api.model
    def _get_mcp_managers(self):
        """Get all active MCP managers"""
        return MCPBusManager._instances

    @api.model
    def _handle_bus_notification(self, message):
        """Handle a bus notification"""
        if not isinstance(message, dict):
            return

        notification_type = message.get('type')
        if notification_type != 'mcp.response':
            return

        # Extract server ID and response data
        payload = message.get('payload', {})
        server_id = payload.get('server_id')
        response_data = payload.get('response')

        if not server_id or not response_data:
            _logger.warning(f"Received incomplete MCP response: {message}")
            return

        # Find the corresponding manager
        manager_key = f"server_{server_id}"
        managers = self._get_mcp_managers()

        if manager_key in managers:
            manager = managers[manager_key]
            # Handle the response
            manager._handle_response(response_data)
        else:
            _logger.warning(f"Received response for unknown MCP server: {server_id}")