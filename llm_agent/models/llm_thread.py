import logging

from odoo import fields, models

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
        
        This method checks that all tool messages have a preceding assistant message
        with matching tool_calls, and removes any tool messages that don't meet this
        requirement to avoid API errors.
        
        Args:
            messages (list): List of messages to validate and clean
            
        Returns:
            list: Cleaned list of messages
        """
        if not messages:
            return messages
            
        # Log message roles and tool_call_id for debugging
        _logger.info(f"Validating {len(messages)} messages")
        for i, msg in enumerate(messages):
            role = msg.get('role', 'unknown')
            tool_call_id = msg.get('tool_call_id', 'none')
            tool_calls = msg.get('tool_calls', [])
            _logger.info(f"Message {i} - Role: {role}, Tool Call ID: {tool_call_id}, Tool Calls: {len(tool_calls)}")
            
        # First pass: Check if there are any tool messages without a preceding assistant message with tool_calls
        for i, msg in enumerate(messages):
            if msg.get('role') == 'tool':
                tool_call_id = msg.get('tool_call_id')
                
                # Look for a preceding assistant message with matching tool_calls
                found_matching_call = False
                for j in range(i-1, -1, -1):
                    prev_msg = messages[j]
                    if prev_msg.get('role') == 'assistant' and prev_msg.get('tool_calls'):
                        for tool_call in prev_msg.get('tool_calls', []):
                            if tool_call.get('id') == tool_call_id:
                                found_matching_call = True
                                break
                        if found_matching_call:
                            break
                
                if not found_matching_call:
                    # This tool message doesn't have a matching assistant message with tool_calls
                    # Remove it from the messages to avoid the API error
                    _logger.warning(f"Removing tool message with ID {tool_call_id} because it has no matching assistant message with tool_calls")
                    messages[i] = None  # Mark for removal
        
        # Second pass: Check all assistant messages with tool_calls and ensure they have corresponding tool messages
        all_tool_call_ids = set()
        all_tool_response_ids = set()
        
        # Collect all tool_call_ids from assistant messages
        for i, msg in enumerate(messages):
            if msg and msg.get('role') == 'assistant' and msg.get('tool_calls'):
                for tool_call in msg.get('tool_calls', []):
                    tool_call_id = tool_call.get('id')
                    if tool_call_id:
                        all_tool_call_ids.add(tool_call_id)
                        _logger.info(f"Found tool_call_id in assistant message: {tool_call_id}")
        
        # Collect all tool_call_ids that have tool responses
        for i, msg in enumerate(messages):
            if msg and msg.get('role') == 'tool' and msg.get('tool_call_id'):
                all_tool_response_ids.add(msg.get('tool_call_id'))
                _logger.info(f"Found tool response for tool_call_id: {msg.get('tool_call_id')}")
        
        # Find missing tool responses
        missing_tool_responses = all_tool_call_ids - all_tool_response_ids
        if missing_tool_responses:
            _logger.warning(f"Found {len(missing_tool_responses)} tool_calls without responses: {missing_tool_responses}")
            
            # Remove tool_calls from assistant messages if they don't have corresponding tool responses
            for i, msg in enumerate(messages):
                if msg and msg.get('role') == 'assistant' and msg.get('tool_calls'):
                    updated_tool_calls = []
                    for tool_call in msg.get('tool_calls', []):
                        tool_call_id = tool_call.get('id')
                        if tool_call_id and tool_call_id not in missing_tool_responses:
                            updated_tool_calls.append(tool_call)
                    
                    if len(updated_tool_calls) < len(msg.get('tool_calls', [])):
                        if updated_tool_calls:
                            # Keep the message but with only the tool_calls that have responses
                            messages[i]['tool_calls'] = updated_tool_calls
                            _logger.info(f"Updated assistant message {i} to only include tool_calls with responses")
                        else:
                            # If no tool_calls remain, remove them entirely
                            messages[i] = {
                                'role': 'assistant',
                                'content': messages[i].get('content') or ""  # Ensure content is never null
                            }
                            _logger.info(f"Removed all tool_calls from assistant message {i}")
        
        # Remove marked messages
        cleaned_messages = [msg for msg in messages if msg is not None]
        _logger.info(f"Validation complete. Original messages: {len(messages)}, Cleaned messages: {len(cleaned_messages)}")
        return cleaned_messages

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
                    raw_output = f"<strong>Tool:</strong> {tool_call['function']['name']}<br><br>"
                    raw_output += f"<strong>Arguments:</strong> <pre><code class='language-json'>{tool_call['function']['arguments']}</code></pre><br>"
                    raw_output += f"<strong>Result:</strong> <pre><code class='language-json'>{tool_call['result']}</code></pre><br>"

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
