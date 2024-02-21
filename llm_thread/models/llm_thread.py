import json
import logging

import emoji

from odoo import api, fields, models

from odoo.addons.llm_mail_message_subtypes.const import (
    LLM_TOOL_RESULT_SUBTYPE_XMLID,
    LLM_USER_SUBTYPE_XMLID,
    LLM_ASSISTANT_SUBTYPE_XMLID,
)

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

    llm_thread_state = fields.Selection(
        [
            ('idle', 'Idle'),
            ('streaming', 'Processing'),
        ],
        string="Processing State",
        default='idle',
        readonly=True,
        required=True,
        copy=False,
        tracking=True,
        help="Reflects the backend processing state of the thread. 'Processing' means the system is working on a response.")

    @api.model_create_multi
    def create(self, vals_list):
        """Set default title if not provided"""
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = f"Chat with {self.model_id.name}"
        return super().create(vals_list)

    def post_llm_response(self, **kwargs):
        """Post a message to the thread with support for tool messages"""
        self.ensure_one()
        subtype_xmlid = kwargs.get("subtype_xmlid")
        if not subtype_xmlid:
            raise ValueError("Subtype XML ID is required for _post_llm_message")

        try:
            subtype = self.env.ref(subtype_xmlid)
        except ValueError: # Catches if XML ID format is wrong or module not installed
             _logger.error(f"Invalid XML ID format or module missing for subtype: {subtype_xmlid}")
             raise MissingError(f"Subtype with XML ID '{subtype_xmlid}' not found.")
        if not subtype.exists():
            raise MissingError(f"Subtype with XML ID '{subtype_xmlid}' not found.")

        body = emoji.demojize(kwargs.get("body"))

        email_from = False # Let Odoo handle default unless we override
        is_tool_result = subtype_xmlid == LLM_TOOL_RESULT_SUBTYPE_XMLID
        is_assistant = subtype_xmlid == LLM_ASSISTANT_SUBTYPE_XMLID
        author_id = kwargs.get("author_id")
        # Handle tool messages
        tool_call_id = kwargs.get("tool_call_id")
        tool_calls = kwargs.get("tool_calls")
        tool_name = kwargs.get("tool_name")
        tool_call_definition = kwargs.get("tool_call_definition")
        tool_call_result = kwargs.get("tool_call_result")

        if not author_id: # AI or System messages
            if is_tool_result:
                tool_name = kwargs.get('tool_name', 'Tool') # Get optional tool name
                email_from = f"{tool_name} <tool@{self.provider_id.name.lower().replace(' ', '')}.ai>"
            elif is_assistant:
                model_name = self.model_id.name or 'Assistant'
                provider_name = self.provider_id.name or 'provider'
                email_from = f"{model_name} <ai@{provider_name.lower().replace(' ', '')}.ai>"

        post_vals = {
            'body': body,
            'message_type': 'comment',
            'subtype_xmlid': subtype_xmlid,
            'author_id': author_id,
            'email_from': email_from or None,
            'partner_ids': [],
        }
        if is_assistant:
            extra_vals = {
                'tool_calls': tool_calls,
            }
        elif is_tool_result:
            extra_vals = {
                'tool_call_id': tool_call_id,
                'tool_call_definition': tool_call_definition,
                'tool_call_result': tool_call_result,
            }
        else:
            extra_vals = {}
        extra_vals = {k: v for k, v in extra_vals.items() if v is not None}

        message = self.message_post(**post_vals)

        if extra_vals:
            message.write(extra_vals)

        return message.message_format()[0]

    def _get_message_history_recordset(self, limit=None):
        """Get messages from the thread

        Args:
            limit: Optional limit on number of messages to retrieve

        Returns:
            mail.message recordset containing the messages
        """
        self.ensure_one()
        subtypes_to_fetch = [
            self.env.ref(LLM_USER_SUBTYPE_XMLID, raise_if_not_found=False),
            self.env.ref(LLM_ASSISTANT_SUBTYPE_XMLID, raise_if_not_found=False),
            self.env.ref(LLM_TOOL_RESULT_SUBTYPE_XMLID, raise_if_not_found=False),
        ]       
        subtype_ids = [st.id for st in subtypes_to_fetch if st]    
        domain = [
            ("model", "=", self._name),
            ("res_id", "=", self.id),
            ("message_type", "=", "comment"),
            ("subtype_id", "in", subtype_ids),
        ]
        messages = self.env["mail.message"].search(
            domain, order="create_date ASC", limit=limit
        )
        return messages

    def get_assistant_response(self, stream=True, system_prompt=None):
        """
        Get assistant response with tool handling.

        This method processes the chat messages, validates them, and handles
        the response from the LLM, including any tool calls and their results.

        Args:
            stream (bool): Whether to stream the response
            system_prompt (str, optional): System prompt to include at the beginning of the messages

        Yields:
            dict: Response chunks with various types (content, tool_start, tool_end, error)
        """
        try:
            messages = self._get_message_history_recordset()
            tool_ids = self.tool_ids.ids if self.tool_ids else None

            # Format messages using the provider (which will handle validation)
            try:
                formatted_messages = self.provider_id.format_messages(
                    messages, system_prompt=system_prompt
                )
            except Exception:
                formatted_messages = self._default_format_messages(
                    messages, system_prompt=system_prompt
                )

            # Process response with possible tool calls
            response_generator = self._chat_with_tools(
                formatted_messages, tool_ids, stream
            )

            # Process the response stream using the helper method
            yield from self._process_llm_response(response_generator)

        except Exception as e:
            _logger.error("Error getting AI response: %s", str(e))
            yield {"type": "error", "error": str(e)}

    def _process_llm_response(self, response_generator):
        """
        Process the LLM response stream, handling content and tool calls.

        Args:
            response_generator: Generator yielding response chunks from the LLM

        Yields:
            dict: Processed response chunks with proper formatting
        """
        content = ""
        assistant_tool_calls = []

        try:
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
                self.post_llm_response(
                    body=content or "", tool_calls=assistant_tool_calls
                )

        except Exception as e:
            _logger.error("Error processing LLM response: %s", str(e))
            yield {"type": "error", "error": str(e)}

    def _default_format_messages(self, messages, system_prompt=None):
        """Format messages generic to the provider

        Args:
            messages: mail.message recordset to format
            system_prompt: Optional system prompt to include at the beginning of the messages

        Returns:
            List of formatted messages in OpenAI-compatible format
        """
        # First use the default implementation from the llm_tool module
        formatted_messages = []

        # Add system prompt if provided
        if system_prompt:
            formatted_messages.append({"role": "system", "content": system_prompt})

        # Format the rest of the messages
        for message in messages:
            formatted_messages.append(self.provider_id._default_format_message(message))

        # Then validate and clean the messages for OpenAI
        return formatted_messages

    def _chat_with_tools(self, messages, tool_ids=None, stream=True):
        """Helper method to chat with tools"""
        # Get available tools if tool_ids provided
        tools = None
        if tool_ids:
            tools = self.env["llm.tool"].browse(tool_ids)

        # Use the provider to handle the chat with tools
        response_generator = self.model_id.chat(
            messages=messages, stream=stream, tools=tools
        )

        # Process the response generator
        for response in response_generator:
            # If there's a tool call, execute it
            if response.get("tool_calls"):
                # For non-streaming responses, we get an array of tool calls
                for tool_call in response.get("tool_calls", []):
                    # Execute the tool
                    tool_name = tool_call["function"]["name"]
                    arguments_str = tool_call["function"]["arguments"]
                    tool_id = tool_call["id"]

                    # Execute the tool
                    tool_result = self.execute_tool(tool_name, arguments_str, tool_id)

                    # Update the tool call with the result
                    tool_call.update(tool_result)

            # If there's a single tool call (streaming case)
            elif response.get("tool_call") and not response.get("tool_call").get(
                "result"
            ):
                tool_call = response.get("tool_call")
                tool_name = tool_call["function"]["name"]
                arguments_str = tool_call["function"]["arguments"]
                tool_id = tool_call["id"]

                # Execute the tool
                tool_result = self.execute_tool(tool_name, arguments_str, tool_id)

                # Update the response with the tool result
                response["tool_call"] = tool_result

            yield response

    def _create_tool_response(self, tool_name, arguments_str, tool_id, result_data):
        """Create a standardized tool response structure

        Args:
            tool_name: Name of the tool
            arguments_str: JSON string of arguments
            tool_id: ID of the tool call
            result_data: Result data to include (will be JSON serialized)

        Returns:
            Dictionary with standardized tool response format
        """
        return {
            "id": tool_id,
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": arguments_str,
            },
            "result": json.dumps(result_data),
        }

    def execute_tool(self, tool_name, arguments_str, tool_id):
        """Execute a tool and return the result

        Args:
            tool_name: Name of the tool to execute
            arguments_str: JSON string of arguments for the tool
            tool_id: ID of the tool call

        Returns:
            Dictionary with tool execution result
        """

        tool = self.env["llm.tool"].search([("name", "=", tool_name)], limit=1)

        if not tool:
            _logger.error(f"Tool '{tool_name}' not found")
            return self._create_tool_response(
                tool_name,
                arguments_str,
                tool_id,
                {"error": f"Tool '{tool_name}' not found"},
            )

        try:
            arguments = json.loads(arguments_str)
            result = tool.execute(arguments)
            return self._create_tool_response(tool_name, arguments_str, tool_id, result)
        except Exception as e:
            _logger.exception(f"Error executing tool {tool_name}: {str(e)}")
            return self._create_tool_response(
                tool_name, arguments_str, tool_id, {"error": str(e)}
            )
