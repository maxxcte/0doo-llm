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

    def get_assistant_response(self, stream=True):
        """Get assistant response with tool handling"""
        try:
            messages = self.get_chat_messages()
            tool_ids = self.tool_ids.ids if self.tool_ids else None

            # Process response with possible tool calls
            response_generator = self._chat_with_tools(messages, tool_ids, stream)

            # Track for follow-up
            content = ""
            tool_messages = []
            assistant_message = None

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
                            "content": content if content else None,
                            "tool_calls": [],
                        }

                    # Add tool call to assistant message
                    assistant_message["tool_calls"].append(
                        {
                            "id": tool_call["id"],
                            "type": "function",
                            "function": {
                                "name": tool_call["function"]["name"],
                                "arguments": tool_call["function"]["arguments"],
                            },
                        }
                    )

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

        except Exception as e:
            _logger.error("Error getting AI response: %s", str(e))
            yield {"type": "error", "error": str(e)}

    def _chat_with_tools(self, messages, tool_ids=None, stream=True):
        """Helper method to chat with tools"""
        return self.model_id.chat(messages=messages, stream=stream, tools=tool_ids)
