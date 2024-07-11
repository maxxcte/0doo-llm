from odoo import http
from odoo.http import request


class LLMAssistantController(http.Controller):
    @http.route("/llm/thread/set_assistant", type="json", auth="user")
    def set_thread_assistant(self, thread_id, assistant_id=False):
        """Set the assistant for a thread

        Args:
            thread_id (int): ID of the thread to update
            assistant_id (int, optional): ID of the assistant to set, or False to clear

        Returns:
            dict: Result of the operation
        """
        thread = request.env["llm.thread"].browse(int(thread_id))
        if not thread.exists():
            return {"success": False, "error": "Thread not found"}

        result = thread.set_assistant(assistant_id)
        return {
            "success": bool(result),
            "thread_id": thread_id,
            "assistant_id": assistant_id,
        }
