import logging

from odoo import api, fields, models

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
    message_ids = fields.One2many(
        comodel_name="mail.message",
        inverse_name="res_id",
        string="Messages",
        domain=lambda self: [("model", "=", self._name)],
    )

    @api.model_create_multi
    def create(self, vals_list):
        """Set default title if not provided"""
        for vals in vals_list:
            if not vals.get("name"):
                vals["name"] = f"Chat with {self.model_id.name}"
        return super().create(vals_list)

    def post_message(self, content, role="user"):
        """Post a message to the thread"""
        _logger.debug("Posting message - role: %s, content: %s", role, content)

        message = self.env["mail.message"].create(
            {
                "model": self._name,
                "res_id": self.id,
                "body": content,
                "message_type": "comment",
            }
        )
        return message

    def get_chat_messages(self, limit=None):
        """Get messages in provider-compatible format"""
        domain = [
            ("model", "=", self._name),
            ("res_id", "=", self.id),
            ("message_type", "=", "comment"),
        ]
        messages = self.env["mail.message"].search(
            domain, order="create_date ASC", limit=limit
        )
        return [msg.to_provider_message() for msg in messages]

    def get_assistant_response(self, stream=True):
        """Get streaming response from assistant based on conversation history"""
        try:
            messages = self.get_chat_messages()
            _logger.debug("Getting assistant response for messages: %s", messages)

            content = ""
            for response in self.model_id.chat(messages, stream=stream):
                if response.get("content"):
                    content += response.get("content", "")
                    yield response

            if content:
                _logger.debug("Got assistant response: %s", content)
        except Exception as e:
            _logger.error("Error getting AI response: %s", str(e))
            yield {"error": str(e)}


class MailMessage(models.Model):
    _inherit = "mail.message"

    def to_provider_message(self):
        """Convert to provider-compatible message format"""
        return {
            "role": "user" if self.author_id else "assistant",
            "content": self.body,
        }