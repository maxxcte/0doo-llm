import logging

import emoji

from odoo import api, fields, models

_logger = logging.getLogger(__name__)


class LLMThread(models.Model):
    _name = "llm.thread"
    _description = "LLM Chat Thread"
    _inherit = ["mail.thread"]
    _order = "write_date DESC"

    name = fields.Char(
        string="Title",
        required=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        required=True,
        ondelete="restrict",
    )
    provider_id = fields.Many2one(
        "llm.provider",
        string="Provider",
        required=True,
        ondelete="restrict",
    )
    model_id = fields.Many2one(
        "llm.model",
        string="Model",
        required=True,
        domain="[('provider_id', '=', provider_id), ('model_use', 'in', ['chat', 'multimodal'])]",
        ondelete="restrict",
    )
    active = fields.Boolean(default=True)
    message_ids = fields.One2many(
        comodel_name="mail.message",
        inverse_name="res_id",
        string="Messages",
        domain=lambda self: [("model", "=", self._name)],
    )

    related_thread_model = fields.Char("Related Thread Model")
    related_thread_id = fields.Integer("Related Thread ID")

    tool_ids = fields.Many2many(
        "llm.tool",
        string="Available Tools",
        help="Tools that can be used by the LLM in this thread",
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Set default title if not provided"""
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = f"Chat with {self.model_id.name}"
        return super().create(vals_list)

    def post_ai_response(self, **kwargs):
        """Post a message to the thread with support for tool messages"""
        _logger.debug("Posting message - kwargs: %s", kwargs)
        body = emoji.demojize(kwargs.get("body"))

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

        
        message = self.message_post(
            body=body,
            message_type="comment",
            author_id=False,  # No author for AI messages
            email_from=f"{self.model_id.name} <ai@{self.provider_id.name.lower()}.ai>",
            partner_ids=[],  # No partner notifications
        )

        return message.message_format()[0]

    def get_chat_messages(self, limit=None):
        """Get messages from the thread
        
        Args:
            limit: Optional limit on number of messages to retrieve
            
        Returns:
            mail.message recordset containing the messages
        """
        domain = [
            ("model", "=", self._name),
            ("res_id", "=", self.id),
            ("message_type", "=", "comment"),
        ]
        messages = self.env["mail.message"].search(
            domain, order="create_date ASC", limit=limit
        )
        return messages

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

            # Format messages using the provider (which will handle validation)
            formatted_messages = self.provider_id.format_messages(messages)

            # Process response with possible tool calls
            response_generator = self._chat_with_tools(formatted_messages, tool_ids, stream)

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



class MailMessage(models.Model):
    _inherit = "mail.message"

    def to_provider_message(self):
        """Convert to provider-compatible message format"""
        return {
            "role": "user" if self.author_id else "assistant",
            "content": self.body or "",  # Ensure content is never null
        }
