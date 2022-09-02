from odoo import fields, models


class ResUsersSettings(models.Model):
    _inherit = 'res.users.settings'

    is_discuss_sidebar_category_llm_open = fields.Boolean(
        string="Is LLM Category Open",
        default=True,
    )

    def set_res_users_settings(self, new_settings):
        # Override to handle LLM category state
        super().set_res_users_settings(new_settings)
        if 'is_discuss_sidebar_category_llm_open' in new_settings:
            self.is_discuss_sidebar_category_llm_open = new_settings['is_discuss_sidebar_category_llm_open']
        return {
            'is_discuss_sidebar_category_llm_open': self.is_discuss_sidebar_category_llm_open,
        }
