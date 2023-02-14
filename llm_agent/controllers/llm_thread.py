import json
import logging

from odoo import http
from odoo.http import Response

from odoo.addons.llm_thread.controllers.llm_thread import LLMThreadController

_logger = logging.getLogger(__name__)


class LLMAgentThreadController(LLMThreadController):
    def generate(self, dbname, env, thread_id):
        """Override generate method to handle tool messages"""
        # Convert string data to bytes for all yields
        yield f"data: {json.dumps({'type': 'start'})}\n\n".encode()

        # Stream responses
        thread = env["llm.thread"].browse(int(thread_id))
        for response in thread.get_assistant_response(stream=True):
            if response.get("type") == "error":
                error_data = f"data: {json.dumps({'type': 'error', 'error': response['error']})}\n\n"
                yield error_data.encode("utf-8")
                break

            elif response.get("type") == "content":
                content_data = f"data: {json.dumps({
                    'type': 'content', 
                    'role': response.get('role', 'assistant'),
                    'content': response.get('content', '')
                })}\n\n"
                yield content_data.encode("utf-8")

            elif response.get("type") == "tool_start":
                tool_start_data = f"data: {json.dumps({
                    'type': 'tool_start',
                    'tool_call_id': response.get('tool_call_id'),
                    'function_name': response.get('function_name'),
                    'arguments': response.get('arguments')
                })}\n\n"
                yield tool_start_data.encode("utf-8")

            elif response.get("type") == "tool_end":
                tool_end_data = f"data: {json.dumps({
                    'type': 'tool_end',
                    'role': response.get('role', 'tool'),
                    'tool_call_id': response.get('tool_call_id'),
                    'content': response.get('content', ''),
                    'formatted_content': response.get('formatted_content', '')
                })}\n\n"
                yield tool_end_data.encode("utf-8")

        # Send end event
        yield f"data: {json.dumps({'type': 'end'})}\n\n".encode()
