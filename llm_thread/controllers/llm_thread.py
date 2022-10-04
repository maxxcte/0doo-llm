import json
import logging

from odoo import api, http, registry
from odoo.http import Response, request

_logger = logging.getLogger(__name__)

class LLMThreadController(http.Controller):
    def generate(self, dbname, env, thread_id):
        """Generate streaming response for the thread"""
        with registry(dbname).cursor() as cr:
            env = api.Environment(cr, env.uid, env.context)
            thread = env["llm.thread"].browse(int(thread_id))

            # Convert string data to bytes for all yields
            yield f"data: {json.dumps({'type': 'start'})}\n\n".encode()

            # Stream responses
            for response in thread.get_assistant_response(stream=True):
                if response.get("error"):
                    error_data = f"data: {json.dumps({'type': 'error', 'error': response['error']})}\n\n"
                    yield error_data.encode("utf-8")
                    break

                if response.get("content"):
                    content_data = f"data: {json.dumps({'type': 'content', 'content': response['content']})}\n\n"
                    yield content_data.encode("utf-8")

            # Send end event
            yield f"data: {json.dumps({'type': 'end'})}\n\n".encode()

    @http.route("/llm/thread/stream_response", type="http", auth="user", csrf=True)
    def stream_response(self, thread_id):
        """Stream assistant responses using server-sent events"""
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }

        return Response(
            self.generate(request.cr.dbname, request.env, thread_id),
            direct_passthrough=True,
            headers=headers,
        )
    
    @http.route("/llm/thread/post_ai_response", type="json", auth="user")
    def post_ai_response(self, thread_id, **kwargs):
        """Post a message to the thread"""
        _logger.debug("Posting message - kwargs: %s", kwargs)
        thread = request.env["llm.thread"].browse(int(thread_id))
        message = thread.post_ai_response(**kwargs)
        return message