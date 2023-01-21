from odoo import fields, models

class LLMThread(models.Model):
    _inherit = "llm.thread"
    
    tool_ids = fields.Many2many(
        'llm.tool',
        string='Available Tools',
        help='Tools that can be used by the LLM in this thread'
    )
    
    def get_assistant_response(self, stream=True):
        """Override to add tools to the response"""
        try:
            messages = self.get_chat_messages()
            
            # Get tool ids if any are specified
            tool_ids = self.tool_ids.ids if self.tool_ids else None
            
            content = ""
            for response in self.model_id.chat(
                messages, 
                stream=stream, 
                tools=tool_ids
            ):
                # Handle normal content
                if response.get("content"):
                    content += response.get("content", "")
                    yield response
                
                # Handle tool calls
                if response.get("tool_call"):
                    # Format tool call for UI
                    tool_call = response.get("tool_call")
                    tool_content = f"**Using tool:** {tool_call['function']['name']}\n"
                    tool_content += f"**Arguments:** ```json\n{tool_call['function']['arguments']}\n```\n"
                    tool_content += f"**Result:** ```json\n{tool_call.get('result', '{}')}\n```\n"
                    
                    yield {
                        "role": "assistant",
                        "content": tool_content
                    }
                    
                    # Add tool result as a new message for the model to use
                    # This simulates the OpenAI tool calling flow
                    messages.append({
                        "role": "assistant", 
                        "content": None,
                        "tool_calls": [{
                            "id": tool_call["id"],
                            "type": "function",
                            "function": {
                                "name": tool_call["function"]["name"],
                                "arguments": tool_call["function"]["arguments"]
                            }
                        }]
                    })
                    
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": tool_call.get("result", "{}")
                    })
            
            if content:
                self._logger.debug("Got assistant response: %s", content)
                
        except Exception as e:
            self._logger.error("Error getting AI response: %s", str(e))
            yield {"error": str(e)}