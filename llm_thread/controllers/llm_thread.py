import logging

from odoo import _, http
from odoo.http import request

from odoo.exceptions import AccessError, MissingError, UserError, ValidationError

_logger = logging.getLogger(__name__)


class LLMThreadController(http.Controller):
    @http.route('/llm/thread/<int:thread_id>/completions', type='json', auth='user', methods=['POST'], csrf=True)
    def thread_completions_create(self, thread_id, message=None, **kwargs): # Method name reflects action
        """
        Adds a user message (prompt) to the thread and triggers the synchronous
        backend processing loop to generate the next completion (assistant response).
        Real-time updates are sent via the Odoo Bus during processing.

        Args:
            thread_id (int): The ID of the llm.thread record (from path).
            message (str): The text content of the user's message/prompt (from JSON payload).
            **kwargs: Catches any other potential parameters (e.g., maybe override model temporarily).

        Returns:
            dict: {'status': 'completed'} on success,
                  {'status': 'error', 'error': str} on failure.
        """
        user_message_body = message # Use the 'message' key from payload
        if not user_message_body or not user_message_body.strip():
             return {'status': 'error', 'error': _('Message body cannot be empty.')}

        try:
            thread = request.env['llm.thread'].browse(thread_id)
            if not thread.exists():
                 raise MissingError(_("Chat Thread not found."))

            # Check access rights (write access seems appropriate to trigger completion)
            thread.check_access_rights('write')
            thread.check_access_rule('write')

            # --- Direct Synchronous Call to the main loop ---
            # Pass user message as it's the prompt for this completion
            thread.start_thread_loop(user_message_body=user_message_body.strip())
            # --- Controller waits here ---

            # If start_thread_loop completes without raising an exception
            return {'status': 'completed'}

        except (AccessError, MissingError, ValidationError, UserError) as e:
            _logger.warning(f"Validation/Access Error creating completion for thread {thread_id}: {e}")
            return {'status': 'error', 'error': str(e)}
        except Exception as e:
            _logger.exception(f"Unexpected error creating completion for thread {thread_id}")
            return {'status': 'error', 'error': _("An unexpected error occurred. Please contact support.")}

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
