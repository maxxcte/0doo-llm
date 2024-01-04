import json
import logging

from odoo import api, http, registry
from odoo.http import Response, request

_logger = logging.getLogger(__name__)


class LLMThreadController(http.Controller):
    def generate(self, dbname, env, thread_id, system_prompt=None):
        """Override generate method to handle tool messages"""
        # Use a cursor block to ensure the cursor remains open for the duration of the generator
        with registry(dbname).cursor() as cr:
            env = api.Environment(cr, env.uid, env.context)

            # Convert string data to bytes for all yields
            yield f"data: {json.dumps({'type': 'start'})}\n\n".encode()

            # Stream responses
            thread = env["llm.thread"].browse(int(thread_id))
            for response in thread.get_assistant_response(
                stream=True, system_prompt=system_prompt
            ):
                if response.get("type") == "error":
                    error_data = f"data: {json.dumps({'type': 'error', 'error': response['error']})}\n\n"
                    yield error_data.encode("utf-8")
                    break

                elif response.get("type") == "content":
                    data = {
                        "type": "content",
                        "role": response.get("role", "assistant"),
                        "content": response.get("content", ""),
                    }
                    content_data = f"data: {json.dumps(data)}\n\n"
                    yield content_data.encode("utf-8")

                elif response.get("type") == "tool_start":
                    data = {
                        "type": "tool_start",
                        "tool_call_id": response.get("tool_call_id"),
                        "function_name": response.get("function_name"),
                        "arguments": response.get("arguments"),
                    }
                    tool_start_data = f"data: {json.dumps(data)}\n\n"
                    yield tool_start_data.encode("utf-8")

                elif response.get("type") == "tool_end":
                    data = {
                        "type": "tool_end",
                        "role": response.get("role", "tool"),
                        "tool_call_id": response.get("tool_call_id"),
                        "content": response.get("content", ""),
                        "formatted_content": response.get("formatted_content", ""),
                    }
                    tool_end_data = f"data: {json.dumps(data)}\n\n"
                    yield tool_end_data.encode("utf-8")

            # Send end event
            yield f"data: {json.dumps({'type': 'end'})}\n\n".encode()

    @http.route("/llm/thread/stream_response", type="http", auth="user", csrf=True)
    def stream_response(self, thread_id, system_prompt=None):
        """Stream assistant responses using server-sent events

        Args:
            thread_id: ID of the thread to stream responses from
            system_prompt: Optional system prompt to include with the agent's system prompt
        """
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }

        return Response(
            self.generate(request.cr.dbname, request.env, thread_id, system_prompt),
            direct_passthrough=True,
            headers=headers,
        )

    @http.route("/llm/thread/post_llm_response", type="json", auth="user")
    def post_llm_response(self, thread_id, **kwargs):
        """Post a message to the thread"""
        _logger.debug("Posting message - kwargs: %s", kwargs)
        thread = request.env["llm.thread"].browse(int(thread_id))
        message = thread.post_llm_response(**kwargs)
        return message
