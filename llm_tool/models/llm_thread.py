import logging

from odoo import fields, models

from ..utils.llm_tool_message_validator import LLMToolMessageValidator

_logger = logging.getLogger(__name__)


class LLMThread(models.Model):
    _inherit = "llm.thread"

    tool_ids = fields.Many2many(
        "llm.tool",
        string="Available Tools",
        help="Tools that can be used by the LLM in this thread",
    )

    def post_ai_response(self, **kwargs):
        """Post a message to the thread with support for tool messages"""
        _logger.debug("Posting message - kwargs: %s", kwargs)
        body = kwargs.get("body")

        # Handle tool messages
        tool_call_id = kwargs.get("tool_call_id")
        subtype_xmlid = kwargs.get("subtype_xmlid")
        tool_calls = kwargs.get("tool_calls")
        tool_name = kwargs.get("tool_name")

        if tool_call_id and subtype_xmlid == "llm_tool.mt_tool_message":
            # Use tool name in email_from if available
            if tool_name:
                email_from = f"{tool_name} <tool@{self.provider_id.name.lower()}.ai>"
            else:
                email_from = f"Tool <tool@{self.provider_id.name.lower()}.ai>"

            message = self.message_post(
                body=body,
                message_type="comment",
                author_id=False,  # No author for AI messages
                email_from=email_from,
                partner_ids=[],  # No partner notifications
                subtype_xmlid=subtype_xmlid,
            )

            # Set the tool_call_id on the message
            message.write({"tool_call_id": tool_call_id})

            return message.message_format()[0]

        # Handle assistant messages with tool calls
        if tool_calls:
            import json

            message = self.message_post(
                body=body,
                message_type="comment",
                author_id=False,  # No author for AI messages
                email_from=f"{self.model_id.name} <ai@{self.provider_id.name.lower()}.ai>",
                partner_ids=[],  # No partner notifications
            )

            # Set the tool_calls on the message
            message.write({"tool_calls": json.dumps(tool_calls)})

            return message.message_format()[0]

        # Default behavior for regular messages
        return super().post_ai_response(**kwargs)

    def _validate_and_clean_messages(self, messages):
        """
        Validate and clean messages to ensure proper tool message structure.

        This method uses the LLMToolMessageValidator class to check that all tool messages
        have a preceding assistant message with matching tool_calls, and removes any
        tool messages that don't meet this requirement to avoid API errors.

        Args:
            messages (list): List of messages to validate and clean

        Returns:
            list: Cleaned list of messages
        """
        # Hardcoded value for verbose logging
        verbose_logging = False

        validator = LLMToolMessageValidator(
            messages, logger=_logger, verbose_logging=verbose_logging
        )
        return validator.validate_and_clean()

    def get_assistant_response(self, stream=True):
        """
        Get assistant response with tool handling.

        This method processes the chat messages, validates them, and handles
        the response from the LLM, including any tool calls and their results.

        Args:
            stream (bool): Whether to stream the response

        Yields:
            dict: Response chunks with various types (content, tool_start, tool_end, error)
        """
        try:
            messages = self.get_chat_messages()
            tool_ids = self.tool_ids.ids if self.tool_ids else None

            # Validate and clean messages to ensure proper tool message structure
            messages = self._validate_and_clean_messages(messages)

            # Process response with possible tool calls
            response_generator = self._chat_with_tools(messages, tool_ids, stream)

            # Process the response stream
            content = ""
            assistant_tool_calls = []

            for response in response_generator:
                # Handle content
                if response.get("content") is not None:
                    content += response.get("content", "")
                    yield {
                        "type": "content",
                        "role": "assistant",
                        "content": response.get("content", ""),
                    }

                # Handle tool calls - these come directly from the provider now
                if response.get("tool_call"):
                    tool_call = response.get("tool_call")
                    assistant_tool_calls.append(
                        {
                            "id": tool_call["id"],
                            "type": tool_call["type"],
                            "function": tool_call["function"],
                        }
                    )

                    # Signal tool call start
                    yield {
                        "type": "tool_start",
                        "tool_call_id": tool_call["id"],
                        "function_name": tool_call["function"]["name"],
                        "arguments": tool_call["function"]["arguments"],
                    }

                    # Display raw tool output
                    raw_output = f"**Arguments:**\n```json\n{tool_call['function']['arguments']}\n```\n\n"
                    raw_output += (
                        f"**Result:**\n```json\n{tool_call['result']}\n```\n\n"
                    )

                    # Signal tool call end with result
                    yield {
                        "type": "tool_end",
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": tool_call["result"],
                        "formatted_content": raw_output,
                    }

            # If we have tool calls, post the assistant message with tool_calls
            if assistant_tool_calls:
                self.post_ai_response(
                    body=content or "", tool_calls=assistant_tool_calls
                )

        except Exception as e:
            _logger.error("Error getting AI response: %s", str(e))
            yield {"type": "error", "error": str(e)}

    def _chat_with_tools(self, messages, tool_ids=None, stream=True):
        """Helper method to chat with tools"""
        return self.model_id.chat(messages=messages, stream=stream, tools=tool_ids)
