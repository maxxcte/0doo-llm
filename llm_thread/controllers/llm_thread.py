import json
from odoo import _, http, api, registry
from odoo.http import request, Response
from odoo.exceptions import MissingError

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

    def _safe_yield(self, data_to_yield):
        """Helper generator to yield data safely, handling BrokenPipeError(Disconnected user)."""
        try:
            yield data_to_yield
            return True
        except BrokenPipeError:
            return False
        except Exception:
            return False

    def _llm_thread_generate(self, dbname, env, thread_id, user_message_body):
        """Generate LLM responses with streaming and safe yielding."""
        with registry(dbname).cursor() as cr:
            env = api.Environment(cr, env.uid, env.context)
            llmThread = env["llm.thread"].browse(int(thread_id))
            if not llmThread.exists():
                yield from self._safe_yield(f"data: {json.dumps({'type': 'error', 'error': 'LLM Thread not found.'})}\n\n".encode())
                return

            client_connected = True
            try:
                for response in llmThread.generate(user_message_body):
                    json_data = json.dumps(response, default=str)
                    success = yield from self._safe_yield(f"data: {json_data}\n\n".encode())
                    if not success:
                        client_connected = False
                        break

            except GeneratorExit:
                # Client disconnected explicitly
                client_connected = False
                if llmThread.exists() and llmThread._read_is_locked_decorated():
                    llmThread._unlock()
                return

            except Exception as e:
                if llmThread.exists() and llmThread._read_is_locked_decorated():
                    llmThread._unlock()

                if client_connected:
                    success = yield from self._safe_yield(f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n".encode())
                    if not success:
                        client_connected = False

            finally:
                if client_connected:
                    yield from self._safe_yield(f"data: {json.dumps({'type': 'done'})}\n\n".encode())

    @http.route('/llm/thread/generate', type="http", auth='user', csrf=True)
    def llm_thread_generate(self, thread_id, message=None, **kwargs):
        headers = {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
        user_message_body = message
        return Response(
            self._llm_thread_generate(request.cr.dbname, request.env, thread_id, user_message_body),
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
