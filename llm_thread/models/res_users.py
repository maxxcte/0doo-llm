from odoo import models


class ResUsers(models.Model):
    _inherit = "res.users"

    def _init_messaging(self):
        values = super()._init_messaging()
        
        # Check if we're in LLM mode from the context
        if self.env.context.get('llm_mode'):
            # Clear regular channels and chats
            values['channels'] = []
            values['chats'] = []
        
        # Add LLM threads
        llm_threads = self.env['llm.thread'].search([])
        values['llm_threads'] = [{
            'id': thread.id,
            'name': thread.name,
            'model': 'llm.thread',
            'isPinned': True,
            'lastMessage': thread.message_ids[0].message_format()[0] if thread.message_ids else False,
        } for thread in llm_threads]
    
        return values