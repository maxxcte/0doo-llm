import logging

from odoo import http
from odoo.http import request
from odoo.exceptions import MissingError
from odoo.tools.translate import _
from ..models.odoo_record_action_thread import OdooRecordActionThread

_logger = logging.getLogger(__name__)


class LLMThreadController(http.Controller):

    @http.route('llm/thread/<int:thread_id>/update', type='json', auth='user', methods=['POST'], csrf=True)
    def llm_thread_update(self, thread_id, **kwargs):
        try:
            thread = request.env['llm.thread'].browse(thread_id)
            if not thread.exists():
                raise MissingError(_("LLM Thread not found."))
            thread.write(kwargs)
            return {'status': 'success'}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
        

    @http.route('/llm/thread/<int:thread_id>/run', type='json', auth='user', methods=['POST'], csrf=True)
    def run(self, thread_id, message=None, **kwargs):
        user_message_body = message
        if not user_message_body or not user_message_body.strip():
            return {'status': 'error', 'error': _('Message body cannot be empty.')}

        try:
            thread = request.env['llm.thread'].browse(thread_id)
            if not thread.exists():
                raise MissingError(_("Chat Thread not found."))
            if thread.state == 'streaming':
                return {'status': 'error', 'error': _("Thread is already processing.")}

            dbname = request.env.cr.dbname
            uid = request.env.uid
            context = request.env.context
            model_name = 'llm.thread'
            method_name = 'start_thread_loop'
            method_kwargs = {'user_message_body': user_message_body.strip()}

            recordActionThread = OdooRecordActionThread(
                dbname=dbname,
                uid=uid,
                context=context,
                model_name=model_name,
                record_id=thread_id,
                method_name=method_name,
                method_kwargs=method_kwargs
            )
            recordActionThread.start()
            return {'status': 'processing_started'}

        except Exception as e:
            return {'status': 'error', 'error': str(e)}

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
