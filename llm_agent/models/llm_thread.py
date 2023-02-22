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
        
        if tool_call_id and subtype_xmlid == "llm_agent.mt_tool_message":
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
        return super(LLMThread, self).post_ai_response(**kwargs)

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
        
        validator = LLMToolMessageValidator(messages, logger=_logger, verbose_logging=verbose_logging)
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
            yield from self._process_response_stream(response_generator)
                
        except Exception as e:
            _logger.error("Error getting AI response: %s", str(e))
            yield {"type": "error", "error": str(e)}
            
    def _process_response_stream(self, response_generator):
        """
        Process the response stream from the LLM, handling content and tool calls.
        
        Args:
            response_generator: Generator yielding response chunks
            
        Yields:
            dict: Processed response chunks
        """
        # Track for follow-up
        content = ""
        tool_messages = []
        assistant_message = None
        assistant_tool_calls = []

        for response in response_generator:
            # Handle content
            if response.get("content") is not None:
                content += response.get("content", "")
                yield {"type": "content", "role": "assistant", "content": response.get("content", "")}

            # Handle tool calls
            if response.get("tool_call"):
                tool_call = response.get("tool_call")
                
                # Process tool call and get related data
                tool_call_data = self._prepare_tool_call_data(tool_call)
                assistant_tool_calls.append(tool_call_data)
                
                # Create or update assistant message
                assistant_message = self._create_or_update_assistant_message(
                    assistant_message, content, tool_call_data
                )
                
                # Create tool message
                tool_message = self._create_tool_message(tool_call)
                tool_messages.append(tool_message)
                
                # Generate and yield tool events
                yield from self._generate_tool_events(tool_call)
                
        # If we have tool calls, post the assistant message with tool_calls
        if assistant_tool_calls:
            self.post_ai_response(
                body=content or "",
                tool_calls=assistant_tool_calls
            )
            
    def _prepare_tool_call_data(self, tool_call):
        """
        Prepare tool call data structure for the assistant message.
        
        Args:
            tool_call (dict): Tool call information
            
        Returns:
            dict: Formatted tool call data
        """
        return {
            "id": tool_call["id"],
            "type": "function",
            "function": {
                "name": tool_call["function"]["name"],
                "arguments": tool_call["function"]["arguments"],
            },
        }
        
    def _create_or_update_assistant_message(self, assistant_message, content, tool_call_data):
        """
        Create a new assistant message or update an existing one with a tool call.
        
        Args:
            assistant_message (dict): Existing assistant message or None
            content (str): Content of the message
            tool_call_data (dict): Tool call data to add
            
        Returns:
            dict: Updated assistant message
        """
        # Create assistant message if not already created
        if not assistant_message:
            assistant_message = {
                "role": "assistant",
                "content": content if content else "",  # Ensure content is never null
                "tool_calls": [],
            }
            
        # Add tool call to assistant message
        assistant_message["tool_calls"].append(tool_call_data)
        
        return assistant_message
        
    def _create_tool_message(self, tool_call):
        """
        Create a tool message from a tool call.
        
        Args:
            tool_call (dict): Tool call information
            
        Returns:
            dict: Tool message
        """
        return {
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": tool_call["result"],
        }
        
    def _generate_tool_events(self, tool_call):
        """
        Generate tool start and end events for streaming.
        
        Args:
            tool_call (dict): Tool call information
            
        Yields:
            dict: Tool events
        """
        # Signal tool call start
        yield {
            "type": "tool_start",
            "tool_call_id": tool_call["id"],
            "function_name": tool_call["function"]["name"],
            "arguments": tool_call["function"]["arguments"]
        }

        # Display raw tool output
        raw_output = f"**Arguments:**\n```json\n{tool_call['function']['arguments']}\n```\n\n"
        raw_output += f"**Result:**\n```json\n{tool_call['result']}\n```\n\n"

        # Signal tool call end with result
        yield {
            "type": "tool_end",
            "role": "tool",
            "tool_call_id": tool_call["id"],
            "content": tool_call["result"],
            "formatted_content": raw_output
        }

    def _chat_with_tools(self, messages, tool_ids=None, stream=True):
        """Helper method to chat with tools"""
        return self.model_id.chat(messages=messages, stream=stream, tools=tool_ids)
