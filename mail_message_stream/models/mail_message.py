import logging
import uuid
from odoo import models, api, SUPERUSER_ID

from ..const import (
    STREAM_START_NOTIFICATION,
    STREAM_CHUNK_NOTIFICATION,
    STREAM_DONE_NOTIFICATION,
)

_logger = logging.getLogger(__name__)

class MailMessageStream(models.Model):
    """
    Inherits mail.message to add methods for sending streaming events
    via Bus following the mail module notification pattern.
    Notifications are sent on the channel of the record the message belongs to.
    """
    _name = 'mail.message'
    _inherit = ['mail.message', 'bus.immediate.send.mixin']

    def _get_bus_stream_channel(self):
        """Gets the channel of the record this message is posted on."""
        self.ensure_one()
        partner_id = self.env.user.partner_id.id
        channel = (self.env.cr.dbname, 'res.partner', partner_id)
        return channel

    def _generate_bus_stream_id(self):
        return str(uuid.uuid4())

    def _notify_stream(self, notification_type, payload_data):
        """Internal helper to structure and send the bus notification."""
        self.ensure_one()
        channel = self._get_bus_stream_channel()
        if not channel:
            return
        
        full_payload = {
            'message_id': self.id,
            'thread_model': self.model,
            'thread_id': self.res_id,
            'data': payload_data or {}
        }

        self._sendone_immediately(channel, notification_type, full_payload)

    def stream_start(self, initial_data=None):
        """Sends 'mail.message/stream_start'. Returns stream_id."""
        self.ensure_one()
        stream_id = self._generate_bus_stream_id()
        data_payload = {'stream_id': stream_id, 'initial_data': initial_data}
        self._notify_stream(STREAM_START_NOTIFICATION, data_payload)
        return stream_id

    def stream_chunk(self, stream_id, chunk):
        """Sends 'mail.message/stream_chunk'."""
        self.ensure_one()
        if not stream_id: return
        data_payload = {'stream_id': stream_id, 'chunk': chunk}
        self._notify_stream(STREAM_CHUNK_NOTIFICATION, data_payload)

    def stream_done(self, stream_id, final_data=None, error=None):
        """Sends 'mail.message/stream_done'."""
        self.ensure_one()
        if not stream_id: return
        data_payload = {'stream_id': stream_id, 'final_data': final_data, 'error': error}
        self._notify_stream(STREAM_DONE_NOTIFICATION, data_payload)