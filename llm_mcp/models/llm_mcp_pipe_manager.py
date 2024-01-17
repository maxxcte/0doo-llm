import subprocess
import threading
import logging
import json

_logger = logging.getLogger(__name__)

class PipeManager:
    _instances = {}
    _lock = threading.Lock()

    def __new__(cls, command=None, args=None):
        # Singleton pattern to ensure only one instance exists per command
        key = f"{command}_{args}"

        with cls._lock:
            if key not in cls._instances:
                instance = super(PipeManager, cls).__new__(cls)
                instance._initialize(command, args)
                cls._instances[key] = instance
            return cls._instances[key]

    def _initialize(self, command, args):
        # Initialize the subprocess with a pipe
        self.command = command
        self.args = args
        self.process = None
        self.stdout = None
        self.stdin = None
        self._initialized = False
        self._request_counter = 0
        self._pending_requests = {}

    def start_process(self):
        """Start or restart the subprocess."""
        with self._lock:
            if self.process is None or self.process.poll() is not None:
                try:
                    cmd = [self.command]
                    if self.args:
                        cmd.extend(self.args.split())

                    _logger.info(f"Starting MCP process with command: {cmd}")

                    self.process = subprocess.Popen(
                        cmd,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True,  # Use text mode for string I/O
                        bufsize=1,  # Line buffering
                    )
                    self.stdin = self.process.stdin
                    self.stdout = self.process.stdout

                    # Initialize the MCP server
                    if not self._initialized:
                        self._initialize_mcp()
                except Exception as e:
                    # Handle startup errors
                    _logger.error(f"Failed to start process: {e}")
                    self.process = None
                    raise

    def _initialize_mcp(self):
        """Initialize the MCP protocol with the server"""
        try:
            # Send initialize request according to MCP protocol
            initialize_request = {
                "jsonrpc": "2.0",
                "id": self._get_next_request_id(),
                "method": "initialize",
                "params": {
                    "clientInfo": {
                        "name": "odoo-llm-mcp",
                        "version": "1.0.0"
                    },
                    "protocolVersion": "0.1.0",
                    "capabilities": {
                        "tools": {}
                    }
                }
            }

            self._write_json(initialize_request)
            response = self._read_json()

            if "result" in response:
                self._initialized = True
                # Send initialized notification according to the protocol
                initialized_notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {}
                }
                self._write_json(initialized_notification)
                return True
            else:
                _logger.error(f"Failed to initialize MCP server: {response.get('error', {}).get('message', 'Unknown error')}")
                return False

        except Exception as e:
            _logger.error(f"Error initializing MCP server: {str(e)}")
            return False

    def _get_next_request_id(self):
        """Get a unique request ID for JSON-RPC requests"""
        with self._lock:
            self._request_counter += 1
            return self._request_counter

    def _write_json(self, data):
        """Write JSON data to the process stdin"""
        with self._lock:
            if self.process is None or self.process.poll() is not None:
                self.start_process()
            try:
                json_str = json.dumps(data)
                self.stdin.write(f"{json_str}\n")
                self.stdin.flush()
            except Exception as e:
                _logger.error(f"Error writing JSON to pipe: {e}")
                self.start_process()  # Attempt to restart
                raise

    def _read_json(self):
        """Read and parse JSON from the process stdout"""
        with self._lock:
            if self.process is None or self.process.poll() is not None:
                self.start_process()
            try:
                line = self.stdout.readline().strip()
                if not line:
                    return None
                return json.loads(line)
            except Exception as e:
                _logger.error(f"Error reading JSON from pipe: {e}")
                self.start_process()
                raise

    def list_tools(self):
        """Send a tools/list request to the server"""
        try:
            request_id = self._get_next_request_id()
            request = {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": "tools/list",
                "params": {}
            }

            self._write_json(request)
            response = self._read_json()

            if "result" in response and "tools" in response["result"]:
                return response["result"]["tools"]
            else:
                error_message = response.get("error", {}).get("message", "Unknown error")
                _logger.error(f"Error listing tools: {error_message}")
                return []

        except Exception as e:
            _logger.error(f"Exception listing tools: {str(e)}")
            return []

    def call_tool(self, tool_name, arguments):
        """Call a tool on the server"""
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

            self._write_json(request)
            response = self._read_json()

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
                return content_result
            else:
                error_message = response.get("error", {}).get("message", "Unknown error")
                _logger.error(f"Error calling tool {tool_name}: {error_message}")
                return {"error": error_message}

        except Exception as e:
            _logger.error(f"Exception calling tool {tool_name}: {str(e)}")
            return {"error": str(e)}

    def close(self):
        """Clean up the process."""
        with self._lock:
            if self.process:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                self.process = None
                self.stdin = None
                self.stdout = None
