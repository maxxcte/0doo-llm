import json
import logging
import shlex
import subprocess
import threading
from contextlib import contextmanager

import odoo
from odoo import api, models

_logger = logging.getLogger(__name__)


class BusSubscriber:
    """
    A minimal bus subscriber that mimics the behavior expected by ImDispatch
    """

    def __init__(self, callback):
        self._channels = set()
        self._subscription = None
        self.callback = callback

    def subscribe(self, channels, last):
        """Called by ImDispatch when subscribing to channels"""
        from odoo.addons.bus.models.bus import BusSubscription

        self._channels = channels
        self._subscription = BusSubscription(channels, last)

    def trigger_notification_dispatching(self):
        """Called by ImDispatch when new notifications arrive"""
        if not self._subscription:
            return

        # Get notifications from the bus using the subscription details
        env = odoo.api.Environment(
            odoo.registry(odoo.service.db.db_list()[0]).cursor(), odoo.SUPERUSER_ID, {}
        )
        try:
            notifications = env["bus.bus"]._poll(
                channels=list(self._subscription.channels),
                last=self._subscription.last_notification_id,
            )

            # Update last notification ID
            if notifications:
                self._subscription.last_notification_id = notifications[-1]["id"]

            # Forward notifications via callback
            for notification in notifications:
                self.callback(notification)

            env.cr.commit()
        except Exception as e:
            _logger.exception("Error polling bus messages: %s", e)
            env.cr.rollback()
        finally:
            env.cr.close()


class LLMMCPBusBridge(models.AbstractModel):
    _name = "llm.mcp.bus.bridge"
    _description = "MCP Bus Bridge to External Process"

    def _get_bridge_thread(self, key=None):
        """Return the bridge thread if it exists"""
        if not hasattr(self.pool, "mcp_bus_bridge_threads"):
            self.pool.mcp_bus_bridge_threads = {}

        if key:
            return self.pool.mcp_bus_bridge_threads.get(key)
        return self.pool.mcp_bus_bridge_threads

    def _set_bridge_thread(self, key, thread):
        """Store the bridge thread in the registry"""
        if not hasattr(self.pool, "mcp_bus_bridge_threads"):
            self.pool.mcp_bus_bridge_threads = {}

        self.pool.mcp_bus_bridge_threads[key] = thread

    @api.model
    def start_bridge(
        self,
        command,
        channels_to_subscribe=None,
        channel_prefixes_to_forward=None,
        server_id=None,
    ):
        """
        Start a bridge thread that forwards bus messages to an external process

        :param command: Command to run (e.g., "python mcp_server.py")
        :param channels_to_subscribe: List of channels to subscribe to in Odoo bus
        :param channel_prefixes_to_forward: List of notification type prefixes to forward
        :param server_id: Optional server ID to uniquely identify this bridge
        """
        if not channels_to_subscribe:
            channels_to_subscribe = ["broadcast"]

        if not channel_prefixes_to_forward:
            channel_prefixes_to_forward = [""]  # Empty string means forward everything

        # Generate a bridge key
        bridge_key = f"mcp_server_{server_id}" if server_id else f"mcp_{command}"

        # Check if thread is already running
        existing_thread = self._get_bridge_thread(bridge_key)
        if existing_thread and existing_thread.is_alive():
            _logger.info(f"Bus bridge {bridge_key} is already running")
            return True

        # Create and start the thread
        bridge_thread = MCPBusBridgeThread(
            db_name=self.env.cr.dbname,
            command=command,
            channels_to_subscribe=channels_to_subscribe,
            channel_prefixes_to_forward=channel_prefixes_to_forward,
            server_id=server_id,
        )
        bridge_thread.start()
        self._set_bridge_thread(bridge_key, bridge_thread)
        return True

    @api.model
    def stop_bridge(self, server_id=None):
        """Stop the bridge thread if it's running"""
        if server_id:
            bridge_key = f"mcp_server_{server_id}"
            bridge_thread = self._get_bridge_thread(bridge_key)
            if bridge_thread and bridge_thread.is_alive():
                bridge_thread.stop()
                bridge_thread.join(timeout=5)
                self._set_bridge_thread(bridge_key, None)
                return True
            return False
        else:
            # Stop all bridges if no server_id provided
            bridges = self._get_bridge_thread()
            stopped = False
            for key, thread in list(bridges.items()):
                if thread and thread.is_alive():
                    thread.stop()
                    thread.join(timeout=5)
                    self._set_bridge_thread(key, None)
                    stopped = True
            return stopped

    @api.model
    def send_message(self, target, notification_type, message):
        """Send a message to the bus"""
        self.env["bus.bus"]._sendone(target, notification_type, message)
        return True


class MCPBusBridgeThread(threading.Thread):
    """Thread that bridges the Odoo bus with an external process"""

    def __init__(
        self,
        db_name,
        command,
        channels_to_subscribe,
        channel_prefixes_to_forward,
        server_id=None,
    ):
        super().__init__(daemon=True, name=f'mcp.bus.bridge-{server_id or "main"}')
        self.db_name = db_name
        self.command = command
        self.channels_to_subscribe = channels_to_subscribe
        self.channel_prefixes_to_forward = channel_prefixes_to_forward
        self.server_id = server_id
        self.stop_event = threading.Event()
        self.process = None
        self.last_notification_id = 0  # Start from 0 to get recent notifications

    def stop(self):
        """Signal the thread to stop"""
        self.stop_event.set()
        if self.process:
            try:
                self.process.terminate()
                self.process.wait(timeout=5)
            except Exception as e:
                _logger.warning(f"Error terminating process: {e}")
                try:
                    self.process.kill()
                except Exception as _e:
                    pass

    def _should_forward_notification(self, notification):
        """Check if a notification should be forwarded based on its type"""
        message = notification.get("message", {})
        notification_type = message.get("type", "")

        # Forward if notification type starts with any of the prefixes
        return any(
            notification_type.startswith(prefix)
            for prefix in self.channel_prefixes_to_forward
        )

    def _on_bus_notification(self, notification):
        """Callback when receiving a notification from the Odoo bus"""
        if self._should_forward_notification(notification):
            try:
                if (
                    self.process and self.process.poll() is None
                ):  # Check if process is running
                    # Convert notification to JSON string and write to process stdin
                    json_str = json.dumps(notification) + "\n"
                    self.process.stdin.write(json_str.encode("utf-8"))
                    self.process.stdin.flush()
                else:
                    # Process died, restart it
                    _logger.warning("External process died, restarting...")
                    self._start_external_process()
            except Exception as e:
                _logger.exception(
                    f"Failed to forward notification to external process: {e}"
                )
                # Try to restart the process
                self._start_external_process()

    def _start_external_process(self):
        """Start the external process"""
        try:
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except Exception as _e:
                    pass

            # Start the process with pipes for stdin, stdout, stderr
            _logger.info(f"Starting external process: {self.command}")
            self.process = subprocess.Popen(
                shlex.split(self.command),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,  # Line buffered
                universal_newlines=False,  # We'll handle encoding ourselves
            )

            # Start thread to read process stdout (for bidirectional communication)
            stdout_thread = threading.Thread(
                target=self._read_process_output, daemon=True
            )
            stdout_thread.start()

            # Start thread to read process stderr (for logging)
            stderr_thread = threading.Thread(
                target=self._read_process_errors, daemon=True
            )
            stderr_thread.start()

            _logger.info(f"Started external process: {self.command}")
            return True
        except Exception as e:
            _logger.exception(f"Failed to start external process: {e}")
            return False

    def _read_process_output(self):
        """Read output from the process (for bidirectional communication)"""
        if not self.process:
            return

        try:
            for line in iter(self.process.stdout.readline, b""):
                if self.stop_event.is_set():
                    break

                try:
                    # Try to parse JSON message from the process
                    message = json.loads(line.decode("utf-8").strip())

                    # If it's a properly formatted message, send it to the bus
                    if isinstance(message, dict):
                        with self._get_environment() as env:
                            # For MCP response handling
                            if "id" in message and (
                                "result" in message or "error" in message
                            ):
                                # This is a response to a request
                                channel = (
                                    f"mcp_response_{self.server_id}"
                                    if self.server_id
                                    else "mcp_response"
                                )
                                env["bus.bus"]._sendone(
                                    channel,
                                    "mcp.response",
                                    {"server_id": self.server_id, "response": message},
                                )
                            elif (
                                "method" in message and message.get("jsonrpc") == "2.0"
                            ):
                                # This is a notification from the MCP server
                                channel = (
                                    f"mcp_notification_{self.server_id}"
                                    if self.server_id
                                    else "mcp_notification"
                                )
                                env["bus.bus"]._sendone(
                                    channel,
                                    "mcp.notification",
                                    {
                                        "server_id": self.server_id,
                                        "notification": message,
                                    },
                                )
                except json.JSONDecodeError:
                    _logger.warning(
                        f"Received non-JSON data from process: {line.decode('utf-8', errors='replace')}"
                    )
                except Exception as e:
                    _logger.exception(
                        f"Error processing message from external process: {e}"
                    )
        except Exception as e:
            if not self.stop_event.is_set():
                _logger.exception(f"Error reading from process stdout: {e}")

    def _read_process_errors(self):
        """Read stderr from the process for logging"""
        if not self.process:
            return

        try:
            for line in iter(self.process.stderr.readline, b""):
                if self.stop_event.is_set():
                    break
                _logger.warning(
                    f"External process error: {line.decode('utf-8', errors='replace').strip()}"
                )
        except Exception as e:
            if not self.stop_event.is_set():
                _logger.exception(f"Error reading from process stderr: {e}")

    @contextmanager
    def _get_environment(self):
        """Get a new Odoo environment with a fresh cursor"""
        registry = odoo.registry(self.db_name)
        with registry.cursor() as cr:
            yield odoo.api.Environment(cr, odoo.SUPERUSER_ID, {})

    def _subscribe_to_bus(self):
        """Subscribe to the Odoo bus channels"""
        try:
            from odoo.addons.bus.models.bus import dispatch

            # Create a wrapper that will receive bus notifications
            self.bus_wrapper = BusSubscriber(self._on_bus_notification)

            # Subscribe to channels
            with self._get_environment() as _env:
                dispatch.subscribe(
                    channels=self.channels_to_subscribe,
                    last=self.last_notification_id,
                    db=self.db_name,
                    websocket=self.bus_wrapper,
                )
            _logger.info(f"Subscribed to bus channels: {self.channels_to_subscribe}")
            return True
        except Exception as e:
            _logger.exception(f"Error subscribing to bus: {e}")
            return False

    def run(self):
        """Main thread loop"""
        _logger.info(f"Starting MCP Bus Bridge thread for server {self.server_id}")

        try:
            # Start the external process
            process_started = self._start_external_process()
            if not process_started:
                _logger.error(
                    "Failed to start external process, stopping bridge thread"
                )
                return

            # Subscribe to the bus
            subscription_ok = self._subscribe_to_bus()
            if not subscription_ok:
                _logger.error("Failed to subscribe to bus, stopping bridge thread")
                return

            # Keep checking the process and restarting if needed
            while not self.stop_event.wait(5):  # Check every 5 seconds
                if self.process and self.process.poll() is not None:
                    _logger.warning(
                        f"External process died with code {self.process.returncode}, restarting..."
                    )
                    self._start_external_process()

        except Exception as e:
            _logger.exception(f"Error in MCP Bus Bridge thread: {e}")

        finally:
            _logger.info(f"MCP Bus Bridge thread stopped for server {self.server_id}")
            if self.process:
                try:
                    self.process.terminate()
                    self.process.wait(timeout=2)
                except Exception as e:
                    _logger.warning(f"Error terminating process: {e}")
                    try:
                        self.process.kill()
                    except Exception as _e:
                        pass
