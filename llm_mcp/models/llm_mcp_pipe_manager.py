import subprocess
import threading
import logging
import json
import time
import traceback
import select
import queue
import os
import signal

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

        # Response queue and reader thread for non-blocking reads
        self._response_queue = queue.Queue()
        self._reader_thread = None
        self._stop_reader = threading.Event()

    def start_process(self):
        """Start or restart the subprocess. Returns True if successful."""
        with self._lock:
            # Stop any existing reader thread
            self._stop_reader_thread()

            if self.process is not None and self.process.poll() is None:
                # Process is already running
                _logger.info(f"MCP process for '{self.command}' is already running")
                # Start reader thread if not running
                self._start_reader_thread()
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

                # Use non-blocking process communication
                self.process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,  # Use text mode for string I/O
                    bufsize=1,  # Line buffering
                    start_new_session=True,  # Put in a new process group to avoid parent signals
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
                        # Start the reader thread
                        self._start_reader_thread()
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

    def _start_reader_thread(self):
        """Start a background thread to read from stdout non-blockingly"""
        if self._reader_thread is not None and self._reader_thread.is_alive():
            return  # Thread already running

        self._stop_reader.clear()
        self._reader_thread = threading.Thread(
            target=self._reader_loop,
            name=f"mcp-reader-{self.command}"
        )
        self._reader_thread.daemon = True
        self._reader_thread.start()
        _logger.info(f"Started reader thread for '{self.command}'")

    def _stop_reader_thread(self):
        """Signal the reader thread to stop and wait for it"""
        if self._reader_thread is not None and self._reader_thread.is_alive():
            _logger.info(f"Stopping reader thread for '{self.command}'")
            self._stop_reader.set()
            self._reader_thread.join(timeout=2)
            if self._reader_thread.is_alive():
                _logger.warning(f"Reader thread for '{self.command}' did not stop cleanly")
            else:
                _logger.info(f"Reader thread for '{self.command}' stopped")
        self._reader_thread = None

    def _reader_loop(self):
        """Background thread to continually read from stdout and queue responses"""
        _logger.info(f"Reader thread started for '{self.command}'")

        while not self._stop_reader.is_set():
            # Check if process is still running
            if self.process is None or self.process.poll() is not None:
                _logger.warning(f"Process '{self.command}' has terminated, reader thread exiting")
                break

            try:
                # Check if stdout has data with a short timeout
                if select.select([self.stdout], [], [], 0.1)[0]:
                    line = self.stdout.readline().strip()
                    if line:
                        _logger.debug(f"Reader thread read: {line}")
                        try:
                            # Parse and queue the response
                            response = json.loads(line)
                            self._response_queue.put(response)
                            _logger.debug(f"Queued response with id: {response.get('id')}")
                        except json.JSONDecodeError as e:
                            _logger.warning(f"Reader thread: Invalid JSON: {e}. Data: {line}")
            except Exception as e:
                if not self._stop_reader.is_set():  # Only log if we're not deliberately stopping
                    _logger.error(f"Error in reader thread: {e}")
                time.sleep(0.1)  # Avoid tight loop in case of repeated errors

        _logger.info(f"Reader thread for '{self.command}' exiting")

    def _initialize_mcp(self):
        """Initialize the MCP protocol with the server. Returns True if successful."""
        if self._initialized:
            _logger.info("MCP protocol already initialized")
            return True

        try:
            # Make sure process is running and reader thread is active
            if not self.start_process():
                _logger.error("Failed to start process for MCP initialization")
                return False

            # Clear the response queue in case there are old messages
            while not self._response_queue.empty():
                try:
                    self._response_queue.get_nowait()
                except queue.Empty:
                    break

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

            request_id = initialize_request["id"]
            _logger.info(f"Initializing MCP protocol with request id {request_id}")

            # Send the request
            self._write_json(initialize_request)

            # Wait for response with timeout
            timeout = 5  # seconds
            start_time = time.time()
            response = None

            while time.time() - start_time < timeout:
                # Check if process is still alive
                if self.process.poll() is not None:
                    exit_code = self.process.returncode
                    stderr_output = "N/A"
                    try:
                        stderr_output = self.process.stderr.read()
                    except:
                        pass
                    _logger.error(f"Process exited during initialization with code {exit_code} and error: {stderr_output}")
                    return False

                try:
                    # Try to get a response with a short timeout
                    response = self._response_queue.get(timeout=0.5)

                    # Check if this is the response we're waiting for
                    if response.get("id") == request_id:
                        _logger.info(f"Received initialization response for id {request_id}")
                        break
                    else:
                        _logger.warning(f"Received response for different id: {response.get('id')}, expecting {request_id}")
                except queue.Empty:
                    # No response yet, continue waiting
                    pass

            if response is None:
                _logger.error(f"Timeout waiting for initialization response after {timeout} seconds")
                return False

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
                _logger.info(f"Sending initialized notification")
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

    def _read_response_with_timeout(self, request_id, timeout=5):
        """Read a response for a specific request ID with timeout"""
        start_time = time.time()

        while time.time() - start_time < timeout:
            # Check if process is still alive
            if self.process.poll() is not None:
                exit_code = self.process.returncode
                stderr_output = "N/A"
                try:
                    stderr_output = self.process.stderr.read()
                except:
                    pass
                _logger.error(f"Process exited while waiting for response {request_id} with code {exit_code} and error: {stderr_output}")
                return None

            try:
                # Try to get a response with a short timeout
                response = self._response_queue.get(timeout=0.5)

                # Check if this is the response we're waiting for
                if response.get("id") == request_id:
                    return response
                else:
                    _logger.warning(f"Received response for id {response.get('id')}, expecting {request_id}")
                    # Put it back in the queue in case someone else is waiting for it
                    self._response_queue.put(response)
            except queue.Empty:
                # No response yet, continue waiting
                pass

        _logger.error(f"Timeout waiting for response to request {request_id} after {timeout} seconds")
        return None

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
            self._write_json(request)

            # Wait for response with timeout
            response = self._read_response_with_timeout(request_id)

            if response is None:
                _logger.error("No response received for tools/list request")
                return None

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

            _logger.info(f"Sending tools/call request for tool '{tool_name}' with id {request_id}")
            self._write_json(request)

            # Wait for response with timeout (tool execution might take longer)
            response = self._read_response_with_timeout(request_id, timeout=30)

            if response is None:
                _logger.error(f"No response received for tools/call request for tool '{tool_name}'")
                return {"error": "No response from MCP server"}

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

    def check_server_health(self):
        """Check if the MCP server is responding correctly and debug issues"""
        _logger.info(f"Checking health of MCP server '{self.command}'")

        # First make sure the process is running
        if self.process is None or self.process.poll() is not None:
            _logger.warning("Server process not running, trying to restart")
            if not self.start_process():
                return {"status": "error", "message": "Failed to start process"}

        # Check stderr for any error messages
        stderr_content = ""
        try:
            if select.select([self.process.stderr], [], [], 0.1)[0]:
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

            # Write the request
            self._write_json(echo_request)

            # Try to read response with timeout
            response = self._read_response_with_timeout(echo_request["id"], timeout=2)

            if response is None:
                return {"status": "error", "message": "Server not responding to echo request"}

            _logger.info(f"Received echo response: {json.dumps(response)}")

            return {
                "status": "ok" if "result" in response else "error",
                "response": response,
                "stderr": stderr_content
            }

        except Exception as e:
            return {"status": "error", "message": f"Error during health check: {str(e)}"}

    def close(self):
        """Clean up the process."""
        with self._lock:
            # Stop reader thread first
            self._stop_reader_thread()

            if self.process:
                _logger.info(f"Closing MCP process for '{self.command}'")
                try:
                    # Try to gracefully terminate the process
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        _logger.warning("Process did not terminate, killing it")
                        # If on Unix, try SIGKILL
                        if hasattr(signal, 'SIGKILL'):
                            try:
                                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
                            except:
                                self.process.kill()
                        else:
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

    def __del__(self):
        """Destructor to ensure process is closed when object is garbage collected"""
        try:
            self.close()
        except:
            pass
