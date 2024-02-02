import logging
import uuid
from odoo import models

STREAM_NOTIFICATION_TYPE = 'mail.message'
 # eg: 'mail.message/stream_start' when sending
STREAM_START_EVENT = 'stream_start'
STREAM_CHUNK_EVENT = 'stream_chunk'
STREAM_DONE_EVENT = 'stream_done'

_logger = logging.getLogger(__name__)

class MailMessageStream(models.Model):
    """
    Inherits mail.message to add methods for sending streaming events
    via Bus TO THE CURRENT USER'S PARTNER CHANNEL.
    """
    _inherit = 'mail.message'

    def _generate_bus_stream_id(self):
        """Generates a unique ID for a streaming session related to this message."""
        return str(uuid.uuid4())

    def _notify_stream(self, event_type, payload_data):
        """Internal helper to structure and send the bus notification TO THE USER."""
        self.ensure_one()
        # Send directly to the current user's partner channel
        # following mail module's pattern
        target_channel = self.env.user.partner_id
        

        if not target_channel:
            _logger.warning(f"Could not determine target partner channel for message {self.id}. Is user logged in?")
            return

        full_payload = {
            'message_id': self.id,
            'message_subtype_xmlid': self.subtype_id.xml_id if self.subtype_id else None, # UI Hint
            'thread_model': self.model,
            'thread_id': self.res_id,
            'data': payload_data or {}
        }

        self.env['bus.bus']._sendone(target_channel, f"{STREAM_NOTIFICATION_TYPE}/{event_type}", full_payload)

    def stream_start(self, data=None):
        """
        Signals the start of streaming content FOR this message instance.
        Sends notification to the current user's partner channel.
        """
        self.ensure_one()
        stream_id = self._generate_bus_stream_id()
        data_payload = {
            'stream_id': stream_id,
            'data': data,
        }
        self._notify_stream(STREAM_START_EVENT, data_payload)
        return stream_id

    def stream_chunk(self, stream_id, data):
        """
        Sends a chunk FOR this message instance to the current user's partner channel.
        """
        self.ensure_one()
        if not stream_id:
             _logger.warning(f"stream_chunk called without stream_id for message {self.id}")
             return
        data_payload = {
            'stream_id': stream_id,
            'data': data,
        }
        self._notify_stream(STREAM_CHUNK_EVENT, data_payload)

    def stream_done(self, stream_id, data=None, error=None):
        """
        Signals the end FOR this message instance to the current user's partner channel.
        """
        self.ensure_one()
        if not stream_id:
             _logger.warning(f"stream_done called without stream_id for message {self.id}")
             return
        data_payload = {
             'stream_id': stream_id,
             'data': data,
             'error': error,
        }
        self._notify_stream(STREAM_DONE_EVENT, data_payload)