import json
import logging
from odoo import api, fields, models, _

_logger = logging.getLogger(__name__)

class LLMProvider(models.Model):
    _inherit = "llm.provider"
    
    def get_available_tools(self, tool_ids=None):
        """Get available tools for this provider
        
        Args:
            tool_ids: Optional specific tool ids to include
            
        Returns:
            List of tool definitions in the format expected by the provider
        """
        domain = [('active', '=', True)]
        
        if tool_ids:
            domain.append(('id', 'in', tool_ids))
        else:
            # Include default tools if no specific tools requested
            domain.append(('default', '=', True))
            
        tools = self.env['llm.tool'].search(domain)
        return tools

    def format_tools_for_provider(self, tools):
        """Format tools for the specific provider"""
        return self._dispatch("format_tools", tools)
        
    # OpenAI specific implementation
    def openai_format_tools(self, tools):
        """Format tools for OpenAI"""
        return [tool.to_tool_definition() for tool in tools]
        
    def openai_chat(self, messages, model=None, stream=False, tools=None, tool_choice="auto"):
        """Send chat messages using OpenAI with tools support"""
        model = self.get_model(model, "chat")
        
        # Prepare request parameters
        params = {
            "model": model.name,
            "messages": messages,
            "stream": stream,
        }
        
        # Add tools if specified
        if tools:
            tool_objects = self.get_available_tools(tools)
            formatted_tools = self.format_tools_for_provider(tool_objects)
            if formatted_tools:
                params["tools"] = formatted_tools
                params["tool_choice"] = tool_choice

        response = self.client.chat.completions.create(**params)
        
        if not stream:
            message = {
                "role": response.choices[0].message.role,
                "content": response.choices[0].message.content or "",  # Handle None content
            }
            
            # Handle tool calls if present
            if hasattr(response.choices[0].message, 'tool_calls') and response.choices[0].message.tool_calls:
                message["tool_calls"] = []
                
                for tool_call in response.choices[0].message.tool_calls:
                    # Find the tool
                    tool = self.env['llm.tool'].search([('name', '=', tool_call.function.name)], limit=1)
                    
                    if tool:
                        # Execute the tool
                        try:
                            arguments = json.loads(tool_call.function.arguments)
                            result = tool.execute(arguments)
                            
                            # Add tool call and result to message
                            message["tool_calls"].append({
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                                "result": json.dumps(result)
                            })
                        except Exception as e:
                            _logger.exception(f"Error executing tool {tool.name}: {str(e)}")
                            message["tool_calls"].append({
                                "id": tool_call.id,
                                "type": "function",
                                "function": {
                                    "name": tool_call.function.name,
                                    "arguments": tool_call.function.arguments,
                                },
                                "result": json.dumps({"error": str(e)})
                            })
                    else:
                        _logger.error(f"Tool {tool_call.function.name} not found")
            
            yield message
        else:
            current_tool_call = None
            tool_call_chunks = {}
            
            for chunk in response:
                delta = chunk.choices[0].delta
                
                # Handle normal content
                if hasattr(delta, 'content') and delta.content is not None:
                    yield {
                        "role": "assistant",
                        "content": delta.content,
                    }
                
                # Handle streaming tool calls
                if hasattr(delta, 'tool_calls') and delta.tool_calls:
                    _logger.info(f"Received tool call chunk: {delta.tool_calls}")
                    
                    for tool_call_chunk in delta.tool_calls:
                        index = tool_call_chunk.index
                        _logger.info(f"Processing tool call chunk with index: {index}")
                        
                        # Initialize tool call data if it's a new one
                        if index not in tool_call_chunks:
                            _logger.info(f"Initializing new tool call with index: {index}")
                            tool_call_chunks[index] = {
                                "id": tool_call_chunk.id,
                                "type": "function",
                                "function": {
                                    "name": "",
                                    "arguments": ""
                                }
                            }
                        
                        # First chunk typically contains id, name and type
                        if tool_call_chunk.id:
                            tool_call_chunks[index]["id"] = tool_call_chunk.id
                            _logger.info(f"Setting tool call ID: {tool_call_chunk.id}")
                        
                        if tool_call_chunk.type:
                            tool_call_chunks[index]["type"] = tool_call_chunk.type
                        
                        # Update function name if present
                        if (hasattr(tool_call_chunk, 'function') and 
                            hasattr(tool_call_chunk.function, 'name') and 
                            tool_call_chunk.function.name):
                            
                            tool_call_chunks[index]["function"]["name"] = tool_call_chunk.function.name
                            _logger.info(f"Setting tool name: '{tool_call_chunk.function.name}'")
                        
                        # Update arguments if present - this continues across multiple chunks
                        if (hasattr(tool_call_chunk, 'function') and 
                            hasattr(tool_call_chunk.function, 'arguments') and 
                            tool_call_chunk.function.arguments is not None):
                            
                            arg_chunk = tool_call_chunk.function.arguments
                            tool_call_chunks[index]["function"]["arguments"] += arg_chunk
                            _logger.info(f"Added argument chunk: '{arg_chunk}' to tool call {index}")
                            _logger.info(f"Current arguments: '{tool_call_chunks[index]['function']['arguments']}'")
                            
                        # Check if we received a complete JSON object - indicating arguments are complete
                        current_args = tool_call_chunks[index]["function"]["arguments"]
                        
                        if current_args and current_args.endswith('}'):
                            try:
                                # Validate JSON is complete by parsing it
                                json.loads(current_args)
                                
                                # Find and execute the tool
                                tool_name = tool_call_chunks[index]["function"]["name"]
                                _logger.info(f"Arguments complete. Looking for tool: '{tool_name}'")
                                
                                if not tool_name:
                                    _logger.warning(f"Empty tool name for index: {index}")
                                    continue
                                    
                                tool = self.env['llm.tool'].search([('name', '=', tool_name)], limit=1)
                                _logger.info(f"Tool search result: {tool}, tool.id: {tool.id if tool else 'Not found'}")
                                
                                if tool:
                                    _logger.info(f"Executing tool '{tool_name}' with arguments: {current_args}")
                                    arguments = json.loads(current_args)
                                    result = tool.execute(arguments)
                                    
                                    # Add result to tool call data
                                    tool_call_chunks[index]["result"] = json.dumps(result)
                                    
                                    # Yield the tool call with result
                                    yield {
                                        "role": "assistant",
                                        "tool_call": tool_call_chunks[index]
                                    }
                                else:
                                    _logger.error(f"Tool '{tool_name}' not found")
                            except json.JSONDecodeError:
                                # JSON not complete yet, continue accumulating
                                _logger.info("JSON arguments incomplete, continuing to accumulate")
                            except Exception as e:
                                _logger.exception(f"Error executing tool: {str(e)}")
                                tool_call_chunks[index]["result"] = json.dumps({"error": str(e)})
                                
                                yield {
                                    "role": "assistant",
                                    "tool_call": tool_call_chunks[index]
                                }
                        
    def chat(self, messages, model=None, stream=False, tools=None, tool_choice="auto"):
        """Send chat messages using this provider"""
        return self._dispatch("chat", messages, model=model, stream=stream, tools=tools, tool_choice=tool_choice)