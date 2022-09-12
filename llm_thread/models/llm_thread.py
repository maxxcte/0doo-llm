import logging

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class LLMThread(models.Model):
    _name = "llm.thread"
    _description = "LLM Chat Thread"
    _inherit = ["mail.thread"]
    _order = "write_date DESC"

    name = fields.Char(
        string="Title",
        required=True,
        tracking=True,
    )
    user_id = fields.Many2one(
        "res.users",
        string="User",
        default=lambda self: self.env.user,
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    provider_id = fields.Many2one(
        "llm.provider",
        string="Provider",
        required=True,
        ondelete="restrict",
        tracking=True,
    )
    model_id = fields.Many2one(
        "llm.model",
        string="Model",
        required=True,
        domain="[('provider_id', '=', provider_id), ('model_use', 'in', ['chat', 'multimodal'])]",
        ondelete="restrict",
        tracking=True,
    )
    active = fields.Boolean(default=True, tracking=True)
    message_ids = fields.One2many('mail.message', 'res_id', domain=[('model', '=', 'llm.thread')])
    state = fields.Selection([
        ('draft', 'Draft'),
        ('active', 'Active'),
        ('closed', 'Closed')
    ], default='active', string='Status')

    @api.model
    def create(self, vals):
        if not vals.get('name'):
            vals['name'] = 'New Chat'
        return super().create(vals)

    def send_message(self, message_content):
        """Send a message in the thread.

        Args:
            message_content (str): The content of the message

        Returns:
            mail.message: The created message record
        """
        self.ensure_one()

        if not message_content:
            raise UserError("Message content cannot be empty")

        message = self.env['mail.message'].create({
            'model': 'llm.thread',
            'res_id': self.id,
            'body': message_content,
            'message_type': 'comment',
            'subtype_id': self.env.ref('mail.mt_comment').id,
        })

        return message
