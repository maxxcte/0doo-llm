import logging
import json
from odoo import http, api, registry
from odoo.http import request, Response
from odoo.exceptions import MissingError
from odoo.tools.translate import _
from ..models.odoo_record_action_thread import OdooRecordActionThread

_logger = logging.getLogger(__name__)


class LLMThreadController(http.Controller):

    @http.route('/llm/thread/<int:thread_id>/update', type='json', auth='user', methods=['POST'], csrf=True)
    def llm_thread_update(self, thread_id, **kwargs):
        try:
            thread = request.env['llm.thread'].browse(thread_id)
            if not thread.exists():
                raise MissingError(_("LLM Thread not found."))
            thread.write(kwargs)
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
        
    def _run(self, dbname, env, thread_id, user_message_body):
        """Override generate method to handle tool messages"""
        # Use a cursor block to ensure the cursor remains open for the duration of the generator
        with registry(dbname).cursor() as cr:
            env = api.Environment(cr, env.uid, env.context)

            # Convert string data to bytes for all yields
            yield f"data: {json.dumps({'type': 'start'})}\n\n".encode()

            # Stream responses
            thread = env["llm.thread"].browse(int(thread_id))
            for response in thread.start_thread_loop(
                user_message_body
            ):
                yield f"data: {json.dumps({'type':'processing'})}\n\n".encode()
            # Send end event
            yield f"data: {json.dumps({'type': 'end'})}\n\n".encode()

    @http.route('/llm/thread/run', type="http", auth='user', csrf=True)
    def run(self, thread_id, message=None, **kwargs):
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
        user_message_body = message
        return Response(
            self._run(request.cr.dbname, request.env, thread_id, user_message_body),
            direct_passthrough=True,
            headers=headers,
        )

    @http.route("/llm/message/vote", type="json", auth="user", methods=["POST"])
    def llm_message_vote(self, message_id, vote_value):
        """Updates the user vote on a specific message by calling the model method."""
        try:
            msg_id = int(message_id)
            vote_val = int(vote_value)
            request.env["mail.message"].set_user_vote(msg_id, vote_val)
            return {"success": True}

        except (ValueError, TypeError):
            return {"error": _("Invalid message ID or vote value format.")}
        except Exception as e:
            return {"error": str(e)}
