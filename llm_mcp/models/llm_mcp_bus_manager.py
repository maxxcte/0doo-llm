import json
import logging
import select
import shlex
import subprocess
import threading
import time

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
                instance = super().__new__(cls)
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

        # Direct process integration
        self.process = None
        self.process_thread = None
        self.stop_event = threading.Event()

        # Response handling
        self._response_event = threading.Event()
        self._responses = {}

    def _start_process(self):
        """Start the MCP server process directly"""
        if self.process and self.process.poll() is None:
            _logger.info(f"MCP process for server {self.server_id} is already running")
            return True

        try:
            # Build command
            full_command = self.command
            if self.args:
                full_command = f"{full_command} {self.args}"

            cmd = shlex.split(full_command)
            _logger.info(f"Starting MCP process with command: {cmd}")

            # Start process
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )

            # Check if process started
            if self.process.poll() is not None:
                stderr_output = "N/A"
                try:
                    stderr_output = self.process.stderr.read()
                except Exception as _e:
                    pass
                _logger.error(
                    f"Process exited immediately with code {self.process.returncode} and error: {stderr_output}"
                )
                return False

            # Start reader thread
            self.stop_event.clear()
            self.process_thread = threading.Thread(
                target=self._process_reader_loop, name=f"mcp-reader-{self.server_id}"
            )
            self.process_thread.daemon = True
            self.process_thread.start()

            # Start error reader thread
            error_thread = threading.Thread(
                target=self._process_error_reader_loop,
                name=f"mcp-error-{self.server_id}",
            )
            error_thread.daemon = True
            error_thread.start()

            _logger.info(
                f"MCP process started successfully for server {self.server_id}"
            )
            return True

        except Exception as e:
            _logger.error(
                f"Failed to start MCP process for server {self.server_id}: {e}"
            )
            return False

    def _stop_process(self):
        """Stop the MCP server process"""
        if not self.process:
            return True

        try:
            self.stop_event.set()

            # Terminate process
            if self.process.poll() is None:
                _logger.info(f"Terminating MCP process for server {self.server_id}")
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    _logger.warning(
                        f"MCP process for server {self.server_id} did not terminate, killing it"
                    )
                    self.process.kill()
                    self.process.wait(timeout=2)

            # Wait for thread to finish
            if self.process_thread and self.process_thread.is_alive():
                self.process_thread.join(timeout=5)

            self.process = None
            self.process_thread = None
            return True
        except Exception as e:
            _logger.error(
                f"Error stopping MCP process for server {self.server_id}: {e}"
            )
            return False

    def _process_reader_loop(self):
        """Reader thread to process stdout from the MCP server"""
        _logger.info(f"Started reader thread for MCP server {self.server_id}")

        try:
            while not self.stop_event.is_set():
                if not self.process or self.process.poll() is not None:
                    _logger.warning(
                        f"MCP process for server {self.server_id} has exited, reader thread stopping"
                    )
                    break

                # Check if stdout has data
                ready_to_read, _, _ = select.select([self.process.stdout], [], [], 0.1)
                if not ready_to_read:
                    continue

                # Read line from stdout
                line = self.process.stdout.readline().strip()
                if not line:
                    continue

                _logger.debug(f"Read from MCP server {self.server_id}: {line}")

                try:
                    # Parse JSON response
                    response = json.loads(line)
                    if isinstance(response, dict) and "id" in response:
                        request_id = response["id"]
                        _logger.info(
                            f"Received response with id {request_id} from MCP server {self.server_id}"
                        )
                        self._responses[request_id] = response
                        self._response_event.set()
                    else:
                        _logger.warning(
                            f"Received unexpected response format from MCP server {self.server_id}: {response}"
                        )
                except json.JSONDecodeError as e:
                    _logger.warning(
                        f"Invalid JSON from MCP server {self.server_id}: {e}, data: {line}"
                    )
                except Exception as e:
                    _logger.error(
                        f"Error processing response from MCP server {self.server_id}: {e}"
                    )

        except Exception as e:
            if not self.stop_event.is_set():
                _logger.error(
                    f"Error in reader thread for MCP server {self.server_id}: {e}"
                )

        _logger.info(f"Reader thread for MCP server {self.server_id} exiting")

    def _process_error_reader_loop(self):
        """Reader thread to process stderr from the MCP server"""
        try:
            while not self.stop_event.is_set():
                if not self.process or self.process.poll() is not None:
                    break

                # Check if stderr has data
                ready_to_read, _, _ = select.select([self.process.stderr], [], [], 0.1)
                if not ready_to_read:
                    continue

                # Read line from stderr
                line = self.process.stderr.readline().strip()
                if not line:
                    continue

                _logger.warning(f"MCP server {self.server_id} stderr: {line}")
        except Exception as e:
            if not self.stop_event.is_set():
                _logger.error(
                    f"Error reading stderr from MCP server {self.server_id}: {e}"
                )

    def _send_message(self, message):
        """Send a message to the MCP server process"""
        if not self.process or self.process.poll() is not None:
            if not self._start_process():
                raise UserError(
                    f"Failed to start MCP server process for server {self.server_id}"
                )

        try:
            # Add request ID if not present
            if "id" not in message:
                message["id"] = self._get_next_request_id()

            # Register this request
            request_id = message["id"]
            self._pending_requests[request_id] = {
                "timestamp": time.time(),
                "message": message,
            }

            # Reset response event
            self._response_event.clear()

            # Send message to process stdin
            json_str = json.dumps(message)
            _logger.info(f"Sending to MCP server {self.server_id}: {json_str}")
            self.process.stdin.write(f"{json_str}\n")
            self.process.stdin.flush()

            return request_id
        except Exception as e:
            _logger.error(f"Error sending message to MCP server {self.server_id}: {e}")
            raise UserError(f"Failed to communicate with MCP server: {e}") from e

    def _get_next_request_id(self):
        """Get a unique request ID for JSON-RPC requests"""
        with self._lock:
            self._request_counter += 1
            return self._request_counter

    def _wait_for_response(self, request_id, timeout=30):
        """Wait for a response from the MCP server"""
        _logger.info(
            f"Waiting for response to request {request_id} from MCP server {self.server_id}"
        )
        start_time = time.time()

        # Wait for response with timeout
        while time.time() - start_time < timeout:
            # Check if process is still running
            if self.process and self.process.poll() is not None:
                exit_code = self.process.returncode
                stderr_output = "N/A"
                try:
                    stderr_output = "".join(self.process.stderr.readlines())
                except Exception as _e:
                    pass
                _logger.error(
                    f"MCP server {self.server_id} process exited with code {exit_code} while waiting for response {request_id}. Error: {stderr_output}"
                )
                return None

            # Check if we have a response
            if request_id in self._responses:
                response = self._responses.pop(request_id)
                if request_id in self._pending_requests:
                    del self._pending_requests[request_id]
                _logger.info(
                    f"Received response for request {request_id} from MCP server {self.server_id}"
                )
                return response

            # Wait for the event with timeout
            self._response_event.wait(0.1)
            self._response_event.clear()

        # Timeout reached
        _logger.error(f"Timeout waiting for response to request {request_id}")

        # Try to check if process is still alive and responsive
        if self.process and self.process.poll() is None:
            # Send a ping to see if process is responsive
            try:
                ping_id = self._get_next_request_id()
                ping = {
                    "jsonrpc": "2.0",
                    "id": ping_id,
                    "method": "echo",
                    "params": {"message": "ping"},
                }
                json_str = json.dumps(ping)
                _logger.info(
                    f"Sending ping to check if MCP server {self.server_id} is responsive: {json_str}"
                )
                self.process.stdin.write(f"{json_str}\n")
                self.process.stdin.flush()

                # Wait briefly for response
                ping_start = time.time()
                while time.time() - ping_start < 5:
                    if ping_id in self._responses:
                        _logger.info(
                            f"MCP server {self.server_id} responded to ping, but not to original request {request_id}"
                        )
                        break
                    time.sleep(0.1)
                else:
                    _logger.error(
                        f"MCP server {self.server_id} is not responding to ping either, may be frozen"
                    )
            except Exception as e:
                _logger.error(f"Error sending ping to MCP server {self.server_id}: {e}")

        # Clean up
        if request_id in self._pending_requests:
            del self._pending_requests[request_id]

        return None

    def _initialize_mcp(self):
        """Initialize the MCP protocol with the server"""
        if self._initialized:
            _logger.info("MCP protocol already initialized")
            return True

        try:
            # Make sure the process is started
            if not self._start_process():
                _logger.error(
                    f"Failed to start process for MCP server {self.server_id}"
                )
                return False

            # Send initialize request according to MCP protocol
            initialize_request = {
                "jsonrpc": "2.0",
                "id": self._get_next_request_id(),
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "odoo-llm-mcp-bus", "version": "1.0.0"},
                    "protocolVersion": "0.1.0",
                    "capabilities": {"tools": {}},
                },
            }

            request_id = initialize_request["id"]
            _logger.info(f"Initializing MCP protocol with request id {request_id}")

            # Send the request
            self._send_message(initialize_request)

            # Wait for response
            # Shorter initial timeout for faster feedback
            response = self._wait_for_response(request_id, timeout=15)

            if response is None:
                _logger.error("No response received for MCP initialization")
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
                    "params": {},
                }
                _logger.info("Sending initialized notification")
                self._send_message(initialized_notification)

                _logger.info(
                    f"MCP server initialized successfully with protocol version {self.protocol_version}"
                )
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
                "params": {},
            }

            _logger.info(f"Sending tools/list request with id {request_id}")
            self._send_message(request)

            # Wait for response
            response = self._wait_for_response(request_id)

            if response is None:
                _logger.error("No response received for tools/list request")
                return None

            if "result" in response and "tools" in response["result"]:
                _logger.info(
                    f"Successfully listed {len(response['result']['tools'])} tools from MCP server"
                )
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
                "params": {"name": tool_name, "arguments": arguments},
            }

            _logger.info(
                f"Sending tools/call request for tool '{tool_name}' with id {request_id}"
            )
            self._send_message(request)

            # Wait for response
            response = self._wait_for_response(
                request_id, timeout=30
            )  # Longer timeout for tool execution

            if response is None:
                _logger.error(
                    f"No response received for tools/call request for tool '{tool_name}'"
                )
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
                    _logger.error(
                        f"Tool '{tool_name}' execution failed: {error_content}"
                    )
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

    def close(self):
        """Close the MCP server connection"""
        return self._stop_process()
