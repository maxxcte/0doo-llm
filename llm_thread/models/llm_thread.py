import logging
import json

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
            try:
                formatted_messages = self.provider_id.format_messages(messages)
            except Exception as e:
                formatted_messages = self._default_format_messages(messages)

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

    def _default_format_messages(self, messages):
        """Format messages for OpenAI API
        
        Args:
            messages: mail.message recordset to format
            
        Returns:
            List of formatted messages in OpenAI-compatible format
        """
        # First use the default implementation from the llm_tool module
        formatted_messages = [];
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
            messages=messages, 
            stream=stream, 
            tools=tools
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
                    tool_result = self.execute_tool(
                        tool_name, 
                        arguments_str, 
                        tool_id
                    )
                    
                    # Update the tool call with the result
                    tool_call.update(tool_result)
                
            # If there's a single tool call (streaming case)
            elif response.get("tool_call") and not response.get("tool_call").get("result"):
                tool_call = response.get("tool_call")
                tool_name = tool_call["function"]["name"]
                arguments_str = tool_call["function"]["arguments"]
                tool_id = tool_call["id"]
                
                # Execute the tool
                tool_result = self.execute_tool(
                    tool_name, 
                    arguments_str, 
                    tool_id
                )
                
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
                {"error": f"Tool '{tool_name}' not found"}
            )

        try:
            arguments = json.loads(arguments_str)
            result = tool.execute(arguments)
            return self._create_tool_response(tool_name, arguments_str, tool_id, result)
        except Exception as e:
            _logger.exception(f"Error executing tool {tool_name}: {str(e)}")
            return self._create_tool_response(
                tool_name, 
                arguments_str, 
                tool_id, 
                {"error": str(e)}
            )