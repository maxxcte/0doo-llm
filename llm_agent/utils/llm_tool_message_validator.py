import logging

_logger = logging.getLogger(__name__)


class LLMToolMessageValidator:
    """
    A dedicated class for validating and cleaning message structures
    for LLM API compatibility.

    This validator ensures that:
    1. All tool messages have a corresponding assistant message with matching tool_calls
    2. All assistant messages with tool_calls have corresponding tool responses
    3. The message structure is valid and consistent for the LLM API

    Usage:
        validator = LLMToolMessageValidator(messages)
        cleaned_messages = validator.validate_and_clean()
    """

    def __init__(self, messages, logger=None, verbose_logging=False):
        """
        Initialize the message validator.

        Args:
            messages (list): List of message dictionaries to validate
            logger (Logger, optional): Custom logger instance
            verbose_logging (bool): Whether to enable verbose logging
        """
        self.messages = messages
        self.logger = logger or logging.getLogger(__name__)
        self.verbose_logging = verbose_logging
        self.tool_call_map = {}  # Maps tool_call_ids to their assistant messages
        self.tool_response_map = {}  # Maps tool_call_ids to their tool response messages

    def validate_and_clean(self):
        """
        Main validation method that orchestrates the validation process.

        Returns:
            list: Cleaned list of messages with invalid entries removed
        """
        if not self.messages:
            return self.messages

        if self.verbose_logging:
            self.log_message_details()

        self.build_message_maps()
        self.remove_orphaned_tool_messages()
        self.handle_missing_tool_responses()

        # Remove any messages marked for removal
        cleaned_messages = [msg for msg in self.messages if msg is not None]

        if self.verbose_logging:
            self.logger.info(
                f"Validation complete. Original messages: {len(self.messages)}, "
                f"Cleaned messages: {len(cleaned_messages)}"
            )

        return cleaned_messages

    def log_message_details(self):
        """Log details about each message for debugging"""
        self.logger.info(f"Validating {len(self.messages)} messages")
        for i, msg in enumerate(self.messages):
            role = msg.get("role", "unknown")
            tool_call_id = msg.get("tool_call_id", "none")
            tool_calls = msg.get("tool_calls", [])
            self.logger.info(
                f"Message {i} - Role: {role}, Tool Call ID: {tool_call_id}, "
                f"Tool Calls: {len(tool_calls)}"
            )

    def build_message_maps(self):
        """
        Build maps connecting tool calls to their responses.

        This creates two mappings:
        1. tool_call_map: Maps tool_call_ids to their originating assistant messages
        2. tool_response_map: Maps tool_call_ids to their tool response messages
        """
        # Map assistant messages with their tool_call_ids
        for i, msg in enumerate(self.messages):
            if not msg:
                continue

            # Process assistant messages with tool calls
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                for tool_call in msg.get("tool_calls", []):
                    tool_call_id = tool_call.get("id")
                    if tool_call_id:
                        self.tool_call_map[tool_call_id] = {
                            "index": i,
                            "tool_call": tool_call,
                            "message": msg,
                        }
                        if self.verbose_logging:
                            self.logger.info(
                                f"Found tool_call_id in assistant message: {tool_call_id}"
                            )

            # Process tool response messages
            if msg.get("role") == "tool" and msg.get("tool_call_id"):
                tool_call_id = msg.get("tool_call_id")
                self.tool_response_map[tool_call_id] = {"index": i, "message": msg}
                if self.verbose_logging:
                    self.logger.info(
                        f"Found tool response for tool_call_id: {tool_call_id}"
                    )

    def remove_orphaned_tool_messages(self):
        """
        Remove tool messages that don't have a matching assistant message with tool_calls.

        This ensures that every tool message corresponds to a valid tool call from an assistant.
        """
        for i, msg in enumerate(self.messages):
            if not msg:
                continue

            if msg.get("role") == "tool":
                tool_call_id = msg.get("tool_call_id")
                if tool_call_id not in self.tool_call_map:
                    self.logger.warning(
                        f"Removing tool message with ID {tool_call_id} because it has no "
                        f"matching assistant message with tool_calls"
                    )
                    self.messages[i] = None

    def handle_missing_tool_responses(self):
        """
        Handle cases where assistant messages have tool_calls without corresponding tool responses.

        This either removes the orphaned tool_calls or updates the assistant message to remove them.
        """
        # Find tool_calls without responses
        missing_responses = set(self.tool_call_map.keys()) - set(
            self.tool_response_map.keys()
        )

        if missing_responses:
            self.logger.warning(
                f"Found {len(missing_responses)} tool_calls without responses: {missing_responses}"
            )

            # Process each assistant message with tool_calls
            for tool_call_id, info in self.tool_call_map.items():
                if tool_call_id in missing_responses:
                    msg_index = info["index"]
                    msg = self.messages[msg_index]

                    # Filter out tool_calls without responses
                    updated_tool_calls = [
                        tc
                        for tc in msg.get("tool_calls", [])
                        if tc.get("id") not in missing_responses
                    ]

                    if updated_tool_calls:
                        # Keep the message but with only the tool_calls that have responses
                        self.messages[msg_index]["tool_calls"] = updated_tool_calls
                        if self.verbose_logging:
                            self.logger.info(
                                f"Updated assistant message {msg_index} to only include "
                                f"tool_calls with responses"
                            )
                    else:
                        # If no tool_calls remain, remove them entirely
                        self.messages[msg_index] = {
                            "role": "assistant",
                            "content": msg.get("content")
                            or "",  # Ensure content is never null
                        }
                        if self.verbose_logging:
                            self.logger.info(
                                f"Removed all tool_calls from assistant message {msg_index}"
                            )
