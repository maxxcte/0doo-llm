import logging

from odoo import _, http, SUPERUSER_ID, api, registry
from odoo.http import request

from odoo.exceptions import AccessError, MissingError, UserError, ValidationError

import threading
_logger = logging.getLogger(__name__)


class LLMThreadController(http.Controller):
    # TODO: Fix this in a correct way, keeping it for testing purposes
    # --- Pass data explicitly to the thread function ---
    def _run(self, dbname, uid, context, thread_id, user_message_body):
        """Target function for the background thread."""
        # DO NOT use 'request' object here

        try:
             # Use api.Environment.manage() for proper cursor/env management in thread
             with api.Environment.manage():
                 # Create registry for the correct DB
                 reg = registry(dbname)
                 with reg.cursor() as new_cr:
                     # Create a new env specific to this thread/cursor using PASSED data
                     # Use SUPERUSER_ID or the original uid depending on permission needs.
                     # Using original uid might be safer but requires the start_thread_loop
                     # and its callees to handle permissions correctly. Let's use original uid.
                     thread_env = api.Environment(new_cr, uid, context)
                     # Browse the record within the new environment
                     thread = thread_env['llm.thread'].browse(thread_id)
                     if thread.exists():
                         _logger.info(f"Background thread starting loop for Thread {thread.id}")
                         # Call the loop method on the record obtained with the thread's env
                         thread.start_thread_loop(user_message_body=user_message_body)
                         _logger.info(f"Background thread finished loop for Thread {thread.id}")
                         # Commit happens automatically if 'with reg.cursor()' exits without error
                     else:
                          _logger.error(f"Background thread could not find Thread {thread_id} in db {dbname}")

        except Exception as e:
             # Log errors happening within the thread
             _logger.exception(f"Error in background thread for Thread {thread_id} (DB: {dbname}): {e}")
             # --- Attempt to update state on error (using separate cursor/env) ---
             try:
                 with api.Environment.manage():
                     reg = registry(dbname) # Need registry again
                     with reg.cursor() as error_cr:
                         # Use SUPERUSER_ID to bypass potential permission issues writing error state
                         error_env = api.Environment(error_cr, SUPERUSER_ID, {})
                         thread_to_update = error_env['llm.thread'].browse(thread_id)
                         if thread_to_update.exists() and thread_to_update.state == 'streaming':
                              thread_to_update.write({'state': 'error'}) # Write error state if using it
                              # OR write back to idle if not using error state:
                              # thread_to_update.write({'state': 'idle'})
                              _logger.info(f"Set thread {thread_id} state back to idle/error due to background exception.")
                         # Commit happens automatically on exit of 'with error_cr'
             except Exception as inner_e:
                  _logger.error(f"Failed to set final state for thread {thread_id} after background error: {inner_e}")

    @http.route('/llm/thread/<int:thread_id>/completions', type='json', auth='user', methods=['POST'], csrf=True)
    def run(self, thread_id, message=None, **kwargs):
        user_message_body = message
        if not user_message_body or not user_message_body.strip():
             return {'status': 'error', 'error': _('Message body cannot be empty.')}

        try:
            # Perform initial checks using the request's environment
            thread = request.env['llm.thread'].browse(thread_id)
            if not thread.exists(): raise MissingError(_("Chat Thread not found."))
            thread.check_access_rights('write')
            thread.check_access_rule('write')
            if thread.state == 'streaming':
                 return {'status': 'error', 'error': _("Thread is already processing.")}

            # --- Prepare arguments for the background thread ---
            dbname = request.env.cr.dbname
            uid = request.env.uid
            context = request.env.context
            thread_args = (dbname, uid, context, thread_id, user_message_body.strip())
            # --------------------------------------------------

            # --- Spawn Background Thread ---
            background_thread = threading.Thread(
                target=self._run,
                args=thread_args, # Pass the prepared arguments
                name=f"llm_thread_loop_{thread_id}"
            )
            # Set daemon based on whether you want these threads to block Odoo shutdown
            # True = Odoo can exit even if thread is running (might leave inconsistent state)
            # False = Odoo waits for thread (can prevent shutdown if thread hangs)
            # Let's default to True for now.
            background_thread.daemon = True
            background_thread.start()
            # ------------------------------

            _logger.info(f"Spawned background thread {background_thread.name} for thread {thread_id} completion.")
            return {'status': 'processing_started'} # Changed status

        # ... (Keep existing exception handling for pre-checks/spawning errors) ...
        except (AccessError, MissingError, ValidationError, UserError) as e:
             _logger.warning(f"Validation/Access Error starting completion for thread {thread_id}: {e}")
             return {'status': 'error', 'error': str(e)}
        except Exception as e:
             _logger.exception(f"Unexpected error starting completion for thread {thread_id}")
             return {'status': 'error', 'error': _("An unexpected error occurred.")}

    @http.route("/llm/message/vote", type="json", auth="user", methods=["POST"])
    def llm_message_vote(self, message_id, vote_value):
        """Updates the user vote on a specific message."""
        try:
            vote_value = int(vote_value)
            if vote_value not in [-1, 1, 0]:
                return {"error": "Invalid vote value. Must be 1, -1, or 0."}

            message = request.env["mail.message"].browse(int(message_id))
            # Basic check if the message exists and belongs to a model the user might see
            # More specific checks could be added if needed (e.g., is it part of an llm.thread?)
            if not message.exists():
                return {"error": "Message not found."}

            # Check if it's an assistant message (no author_id)
            # Although the UI should only show votes for assistant messages,
            # this adds a layer of verification.
            if message.author_id:
                return {"error": "Voting is only allowed on assistant messages."}

            message.sudo().write({"user_vote": vote_value})
            return {"success": True, "message_id": message.id, "new_vote": vote_value}

        except Exception as e:
            # Log the exception?
            return {"error": str(e)}
