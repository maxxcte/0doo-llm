import subprocess
import threading
import logging
import json
import time
import traceback

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
                instance._init_properties(command, args)
                cls._instances[key] = instance
            return cls._instances[key]

    def _init_properties(self, command, args):
        """Initialize instance properties without starting the process"""
        self.command = command
        self.args = args
        self.process = None
        self.stdout = None
        self.stdin = None
        self._initialized = False
        self._request_counter = 0
        self._pending_requests = {}
        self.protocol_version = None
        self.server_info = None
        self._process_start_attempts = 0
        self._max_start_attempts = 3
        self._process_start_timeout = 10  # seconds

    def start_process(self):
        """Start or restart the subprocess. Returns True if successful."""
        with self._lock:
            if self.process is not None and self.process.poll() is None:
                # Process is already running
                _logger.info(f"MCP process for '{self.command}' is already running")
                return True

            # Clear any previous process state
            if self.process is not None:
                _logger.info(f"Terminating existing MCP process for '{self.command}'")
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except Exception as e:
                    _logger.warning(f"Error terminating process: {e}")
                    try:
                        self.process.kill()
                    except Exception as e2:
                        _logger.warning(f"Error killing process: {e2}")
                        pass

            # Increment attempt counter
            self._process_start_attempts += 1
            if self._process_start_attempts > self._max_start_attempts:
                _logger.error(f"Exceeded maximum process start attempts ({self._max_start_attempts}) for '{self.command}'")
                return False

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

                # Check if process started correctly
                start_time = time.time()
                while time.time() - start_time < self._process_start_timeout:
                    if self.process.poll() is not None:
                        # Process exited
                        exit_code = self.process.returncode
                        stderr_output = self.process.stderr.read()
                        _logger.error(f"Process exited immediately with code {exit_code} and error: {stderr_output}")
                        return False

                    # Process is still running, which is good
                    if self.stdin and self.stdout:
                        _logger.info(f"MCP process started successfully for '{self.command}'")
                        # Check if there's any initial output
                        if self.stdout.readable() and not self.process.poll():
                            try:
                                # Non-blocking read if possible
                                initial_output = self.process.stderr.read(1024)
                                if initial_output:
                                    _logger.info(f"Initial stderr output: {initial_output}")
                            except Exception as e:
                                _logger.warning(f"Error reading initial stderr: {e}")
                        return True

                    # Wait a bit before checking again
                    time.sleep(0.1)

                # Timeout reached
                _logger.error(f"Timed out waiting for process '{self.command}' to start")
                return False

            except Exception as e:
                _logger.error(f"Failed to start process '{self.command}': {e}\n{traceback.format_exc()}")
                self.process = None
                self.stdin = None
                self.stdout = None
                return False

    def check_server_health(self):
        """Check if the MCP server is responding correctly and debug issues"""
        _logger.info(f"Checking health of MCP server '{self.command}'")

        # First make sure the process is running
        if self.process is None or self.process.poll() is not None:
            _logger.warning("Server process not running, trying to restart")
            if not self.start_process():
                return {"status": "error", "message": "Failed to start process"}

        # Try to read any pending output
        pending_output = []
        try:
            import select
            while select.select([self.stdout], [], [], 0.1)[0]:  # Check if stdout has data
                line = self.stdout.readline()
                if not line:
                    break
                pending_output.append(line.strip())
        except Exception as e:
            _logger.warning(f"Error reading pending output: {e}")

        if pending_output:
            _logger.info(f"Found pending output: {pending_output}")

        # Check stderr for any error messages
        stderr_content = ""
        try:
            if self.process.stderr.readable():
                # Try non-blocking read
                import io
                stderr_content = self.process.stderr.read(1024)
        except Exception as e:
            _logger.warning(f"Error reading stderr: {e}")

        if stderr_content:
            _logger.warning(f"Server stderr output: {stderr_content}")

        # Try a simple echo request to test communication
        try:
            echo_request = {
                "jsonrpc": "2.0",
                "id": self._get_next_request_id(),
                "method": "echo",  # This might not be part of MCP, but many RPC servers support it
                "params": {"message": "ping"}
            }

            _logger.info(f"Sending echo test request: {json.dumps(echo_request)}")

            # Write directly to stdin to avoid circular dependency
            try:
                echo_json = json.dumps(echo_request)
                self.stdin.write(f"{echo_json}\n")
                self.stdin.flush()
            except Exception as e:
                return {"status": "error", "message": f"Failed to write to server: {str(e)}"}

            # Try to read response with timeout
            import select
            ready_to_read, _, _ = select.select([self.stdout], [], [], 2)
            if not ready_to_read:
                return {"status": "error", "message": "Server not responding to echo request"}

            response_line = self.stdout.readline().strip()
            if not response_line:
                return {"status": "error", "message": "Server returned empty response to echo"}

            _logger.info(f"Received echo response: {response_line}")

            try:
                response = json.loads(response_line)
                return {
                    "status": "ok" if "result" in response else "error",
                    "response": response,
                    "stderr": stderr_content
                }
            except json.JSONDecodeError:
                return {
                    "status": "error",
                    "message": "Server returned invalid JSON",
                    "response": response_line,
                    "stderr": stderr_content
                }

        except Exception as e:
            return {"status": "error", "message": f"Error during health check: {str(e)}"}

    def _initialize_mcp(self):
        """Initialize the MCP protocol with the server. Returns True if successful."""
        if self._initialized:
            _logger.info("MCP protocol already initialized")
            return True

        # First check if there's any pending output that could interfere with communication
        health_check = self.check_server_health()
        if health_check.get("status") == "error":
            _logger.warning(f"Health check failed before initialization: {health_check.get('message')}")
            # Continue anyway, as the health check might fail for servers not supporting echo

        try:
            # Make sure process is running
            if not self.start_process():
                _logger.error("Failed to start process for MCP initialization")
                return False

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

            _logger.info(f"Initializing MCP protocol with request: {json.dumps(initialize_request)}")

            # Direct write to avoid any potential circular issues
            initialize_json = json.dumps(initialize_request)
            self.stdin.write(f"{initialize_json}\n")
            self.stdin.flush()

            # Read with timeout and retry
            response = None
            max_attempts = 3
            attempt = 0

            while response is None and attempt < max_attempts:
                attempt += 1
                _logger.info(f"Reading initialization response (attempt {attempt}/{max_attempts})")

                # Check if the process is still alive
                if self.process.poll() is not None:
                    exit_code = self.process.returncode
                    stderr_output = self.process.stderr.read()
                    _logger.error(f"Process exited during initialization with code {exit_code} and error: {stderr_output}")
                    return False

                # Try to read with timeout
                import select
                ready_to_read, _, _ = select.select([self.stdout], [], [], 3)
                if not ready_to_read:
                    _logger.warning(f"No data received after 3 seconds (attempt {attempt})")
                    # Check stderr for any clues
                    try:
                        stderr_content = self.process.stderr.read(1024)
                        if stderr_content:
                            _logger.warning(f"Stderr content: {stderr_content}")
                    except:
                        pass
                    continue

                line = self.stdout.readline().strip()
                if not line:
                    _logger.warning(f"Empty line received (attempt {attempt})")
                    # Wait a bit before retrying
                    time.sleep(1)
                    continue

                _logger.info(f"Received raw data: {line}")

                try:
                    response = json.loads(line)
                except json.JSONDecodeError as e:
                    _logger.error(f"Invalid JSON received: {e}. Data: '{line}'")
                    # If it's not valid JSON, it might be some startup message
                    # Wait a bit and try the next line
                    time.sleep(0.5)
                    continue

            if response is None:
                _logger.error("Failed to get valid response after multiple attempts")
                return False

            _logger.info(f"Received initialization response: {json.dumps(response)}")

            if response and "result" in response:
                self._initialized = True

                # Store protocol information
                if "protocolVersion" in response["result"]:
                    self.protocol_version = response["result"]["protocolVersion"]
                if "serverInfo" in response["result"]:
                    self.server_info = response["result"]["serverInfo"]

                # Send initialized notification according to the protocol
                initialized_notification = {
                    "jsonrpc": "2.0",
                    "method": "notifications/initialized",
                    "params": {}
                }
                _logger.info(f"Sending initialized notification: {json.dumps(initialized_notification)}")
                self._write_json(initialized_notification)

                _logger.info(f"MCP server initialized successfully with protocol version {self.protocol_version}")
                return True
            else:
                error_message = "Unknown error"
                if response and "error" in response:
                    error_message = response["error"].get("message", "Unknown error")
                _logger.error(f"Failed to initialize MCP server: {error_message}")
                return False

        except Exception as e:
            _logger.error(f"Error initializing MCP server: {str(e)}\n{traceback.format_exc()}")
            return False
    def _get_next_request_id(self):
        """Get a unique request ID for JSON-RPC requests"""
        with self._lock:
            self._request_counter += 1
            return self._request_counter

    def _write_json(self, data):
        """Write JSON data to the process stdin"""
        with self._lock:
            # Ensure process is running
            if self.process is None or self.process.poll() is not None:
                _logger.warning("Process not running before write, attempting to start")
                if not self.start_process():
                    error_msg = "Failed to start process for writing"
                    _logger.error(error_msg)
                    raise IOError(error_msg)

            try:
                json_str = json.dumps(data)
                _logger.info(f"Writing to MCP server: {json_str}")
                self.stdin.write(f"{json_str}\n")
                self.stdin.flush()
                _logger.debug(f"Successfully wrote and flushed data to MCP server")
            except Exception as e:
                _logger.error(f"Error writing JSON to pipe: {e}\n{traceback.format_exc()}")
                # Try to restart process
                if not self.start_process():
                    raise IOError(f"Failed to restart process after write error: {e}")
                raise IOError(f"Error communicating with MCP server: {e}")

    def _read_json(self, timeout=None):
        """Read and parse JSON from the process stdout"""
        with self._lock:
            # Ensure process is running
            if self.process is None or self.process.poll() is not None:
                _logger.warning("Process not running before read, attempting to start")
                if not self.start_process():
                    error_msg = "Failed to start process for reading"
                    _logger.error(error_msg)
                    raise IOError(error_msg)

            try:
                # Handle timeout if specified
                if timeout:
                    import select
                    ready_to_read, _, _ = select.select([self.stdout], [], [], timeout)
                    if not ready_to_read:
                        _logger.warning(f"Read timeout after {timeout} seconds")
                        return None

                line = self.stdout.readline().strip()
                if not line:
                    stderr_content = "N/A"
                    try:
                        if self.process.poll() is not None:
                            stderr_content = self.process.stderr.read(1024)
                        else:
                            stderr_content = "Process still running, no stderr available"
                    except:
                        pass
                    _logger.warning(f"Read empty line from MCP server. stderr: {stderr_content}")
                    return None

                _logger.info(f"Read from MCP server: {line}")
                try:
                    return json.loads(line)
                except json.JSONDecodeError as e:
                    _logger.error(f"Invalid JSON received from server: {e}. Data: {line}")
                    return None
            except json.JSONDecodeError as e:
                _logger.error(f"Invalid JSON received from server: {e}")
                return None
            except Exception as e:
                _logger.error(f"Error reading JSON from pipe: {e}\n{traceback.format_exc()}")
                # Try to restart process
                if not self.start_process():
                    raise IOError(f"Failed to restart process after read error: {e}")
                raise IOError(f"Error communicating with MCP server: {e}")

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

            _logger.info(f"Sending tools/list request: {json.dumps(request)}")
            self._write_json(request)
            response = self._read_json()

            if response is None:
                _logger.error("No response received for tools/list request")
                return None

            _logger.info(f"Received tools/list response: {json.dumps(response)}")

            if response and "result" in response and "tools" in response["result"]:
                _logger.info(f"Successfully listed {len(response['result']['tools'])} tools from MCP server")
                return response["result"]["tools"]
            else:
                error_message = "Unknown error"
                if response and "error" in response:
                    error_message = response["error"].get("message", "Unknown error")
                _logger.error(f"Error listing tools: {error_message}")
                return None

        except Exception as e:
            _logger.error(f"Exception listing tools: {str(e)}\n{traceback.format_exc()}")
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

            _logger.info(f"Sending tools/call request for tool '{tool_name}': {json.dumps(request)}")
            self._write_json(request)
            response = self._read_json()

            if response is None:
                _logger.error(f"No response received for tools/call request for tool '{tool_name}'")
                return {"error": "No response from MCP server"}

            _logger.info(f"Received tools/call response for tool '{tool_name}': {json.dumps(response)}")

            if response and "result" in response:
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
                if response and "error" in response:
                    error_message = response["error"].get("message", "Unknown error")
                _logger.error(f"Error calling tool {tool_name}: {error_message}")
                return {"error": error_message}

        except Exception as e:
            _logger.error(f"Exception calling tool {tool_name}: {str(e)}\n{traceback.format_exc()}")
            return {"error": str(e)}

    def close(self):
        """Clean up the process."""
        with self._lock:
            if self.process:
                _logger.info(f"Closing MCP process for '{self.command}'")
                try:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        _logger.warning("Process did not terminate, killing it")
                        self.process.kill()
                        self.process.wait(timeout=2)
                except Exception as e:
                    _logger.error(f"Error terminating process: {e}")
                finally:
                    self.process = None
                    self.stdin = None
                    self.stdout = None
                    # We don't reset _initialized here as it's about protocol initialization,
                    # not process state

            _logger.info("MCP pipe manager closed")
