from odoo import http
from odoo.http import request


class LLMAgentController(http.Controller):
    @http.route('/llm/thread/set_agent', type='json', auth="user")
    def set_thread_agent(self, thread_id, agent_id=False):
        """Set the agent for a thread
        
        Args:
            thread_id (int): ID of the thread to update
            agent_id (int, optional): ID of the agent to set, or False to clear
            
        Returns:
            dict: Result of the operation
        """
        thread = request.env['llm.thread'].browse(int(thread_id))
        if not thread.exists():
            return {'success': False, 'error': 'Thread not found'}
            
        result = thread.set_agent(agent_id)
        return {
            'success': bool(result),
            'thread_id': thread_id,
            'agent_id': agent_id,
        }
