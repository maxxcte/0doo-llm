import logging

from odoo import fields, models

_logger = logging.getLogger(__name__)


class MessageValidator:
    """
    A dedicated class for validating and cleaning message structures
    for OpenAI API compatibility.
    """
    def __init__(self, messages, logger=None):
        self.messages = messages
        self.logger = logger or logging.getLogger(__name__)
        self.tool_call_map = {}  # Maps tool_call_ids to their assistant messages
        self.tool_response_map = {}  # Maps tool_call_ids to their tool response messages
    
    def validate_and_clean(self):
        """Main validation method that orchestrates the validation process"""
        if not self.messages:
            return self.messages
        
        self.log_message_details()
        self.build_message_maps()
        self.remove_orphaned_tool_messages()
        self.handle_missing_tool_responses()
        
        # Remove any messages marked for removal
        cleaned_messages = [msg for msg in self.messages if msg is not None]
        self.logger.info(f"Validation complete. Original messages: {len(self.messages)}, Cleaned messages: {len(cleaned_messages)}")
        return cleaned_messages
    
    def log_message_details(self):
        """Log details about each message for debugging"""
        self.logger.info(f"Validating {len(self.messages)} messages")
        for i, msg in enumerate(self.messages):
            role = msg.get('role', 'unknown')
            tool_call_id = msg.get('tool_call_id', 'none')
            tool_calls = msg.get('tool_calls', [])
            self.logger.info(f"Message {i} - Role: {role}, Tool Call ID: {tool_call_id}, Tool Calls: {len(tool_calls)}")
    
    def build_message_maps(self):
        """Build maps connecting tool calls to their responses"""
        # Map assistant messages with their tool_call_ids
        for i, msg in enumerate(self.messages):
            if msg and msg.get('role') == 'assistant' and msg.get('tool_calls'):
                for tool_call in msg.get('tool_calls', []):
                    tool_call_id = tool_call.get('id')
                    if tool_call_id:
                        self.tool_call_map[tool_call_id] = {
                            'index': i,
                            'tool_call': tool_call,
                            'message': msg
                        }
                        self.logger.info(f"Found tool_call_id in assistant message: {tool_call_id}")
            
            # Map tool responses with their tool_call_ids
            if msg and msg.get('role') == 'tool' and msg.get('tool_call_id'):
                tool_call_id = msg.get('tool_call_id')
                self.tool_response_map[tool_call_id] = {
                    'index': i,
                    'message': msg
                }
                self.logger.info(f"Found tool response for tool_call_id: {tool_call_id}")
    
    def remove_orphaned_tool_messages(self):
        """Remove tool messages that don't have a matching assistant message with tool_calls"""
        for i, msg in enumerate(self.messages):
            if msg and msg.get('role') == 'tool':
                tool_call_id = msg.get('tool_call_id')
                if tool_call_id not in self.tool_call_map:
                    self.logger.warning(f"Removing tool message with ID {tool_call_id} because it has no matching assistant message with tool_calls")
                    self.messages[i] = None
    
    def handle_missing_tool_responses(self):
        """Handle cases where assistant messages have tool_calls without corresponding tool responses"""
        # Find tool_calls without responses
        missing_responses = set(self.tool_call_map.keys()) - set(self.tool_response_map.keys())
        
        if missing_responses:
            self.logger.warning(f"Found {len(missing_responses)} tool_calls without responses: {missing_responses}")
            
            # Process each assistant message with tool_calls
            for tool_call_id, info in self.tool_call_map.items():
                if tool_call_id in missing_responses:
                    msg_index = info['index']
                    msg = self.messages[msg_index]
                    
                    # Filter out tool_calls without responses
                    updated_tool_calls = [
                        tc for tc in msg.get('tool_calls', [])
                        if tc.get('id') not in missing_responses
                    ]
                    
                    if updated_tool_calls:
                        # Keep the message but with only the tool_calls that have responses
                        self.messages[msg_index]['tool_calls'] = updated_tool_calls
                        self.logger.info(f"Updated assistant message {msg_index} to only include tool_calls with responses")
                    else:
                        # If no tool_calls remain, remove them entirely
                        self.messages[msg_index] = {
                            'role': 'assistant',
                            'content': msg.get('content') or ""  # Ensure content is never null
                        }
                        self.logger.info(f"Removed all tool_calls from assistant message {msg_index}")


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
        
        This method uses the MessageValidator class to check that all tool messages 
        have a preceding assistant message with matching tool_calls, and removes any 
        tool messages that don't meet this requirement to avoid API errors.
        
        Args:
            messages (list): List of messages to validate and clean
        
        Returns:
            list: Cleaned list of messages
        """
        validator = MessageValidator(messages, logger=_logger)
        return validator.validate_and_clean()

    def get_assistant_response(self, stream=True):
        """Get assistant response with tool handling"""
        try:
            messages = self.get_chat_messages()
            tool_ids = self.tool_ids.ids if self.tool_ids else None

            # Validate and clean messages to ensure proper tool message structure
            messages = self._validate_and_clean_messages(messages)

            # Process response with possible tool calls
            response_generator = self._chat_with_tools(messages, tool_ids, stream)

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

                    # Create assistant message if not already created
                    if not assistant_message:
                        assistant_message = {
                            "role": "assistant",
                            "content": content if content else "",  # Ensure content is never null
                            "tool_calls": [],
                        }

                    # Add tool call to assistant message
                    tool_call_data = {
                        "id": tool_call["id"],
                        "type": "function",
                        "function": {
                            "name": tool_call["function"]["name"],
                            "arguments": tool_call["function"]["arguments"],
                        },
                    }
                    
                    assistant_message["tool_calls"].append(tool_call_data)
                    assistant_tool_calls.append(tool_call_data)

                    # Create tool message
                    tool_messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": tool_call["id"],
                            "content": tool_call["result"],
                        }
                    )

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
                    
            # If we have tool calls, post the assistant message with tool_calls
            if assistant_tool_calls:
                self.post_ai_response(
                    body=content or "",
                    tool_calls=assistant_tool_calls
                )

        except Exception as e:
            _logger.error("Error getting AI response: %s", str(e))
            yield {"type": "error", "error": str(e)}

    def _chat_with_tools(self, messages, tool_ids=None, stream=True):
        """Helper method to chat with tools"""
        return self.model_id.chat(messages=messages, stream=stream, tools=tool_ids)
