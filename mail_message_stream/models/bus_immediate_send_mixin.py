# -*- coding: utf-8 -*-
import logging
from odoo import api, models, SUPERUSER_ID

_logger = logging.getLogger(__name__)

class BusImmediateSendMixin(models.AbstractModel):
    """
    Mixin class to provide a method for sending bus notifications immediately
    using a separate database cursor, bypassing the main transaction's commit delay.

    This is useful for scenarios like streaming responses where notifications
    need to be sent as soon as possible, rather than waiting for the main
    request/operation to complete and commit.

    WARNING: Because the commit is immediate and separate, the notification
             might reach the client *before* the main transaction commits.
             If the main transaction later rolls back, the client will have
             received a notification about a state that never became permanent.
             Client-side logic should be aware of this possibility if data
             consistency shown to the user is critical.
    """
    _name = 'bus.immediate.send.mixin'
    _description = 'Bus Immediate Send Mixin'

    def _send_one_immediately(self, channel, notification_type, payload, user_id=SUPERUSER_ID):
        """
        Sends a bus message using a separate, immediately committed cursor.

        :param channel: The target bus channel (e.g., a partner record, a user record,
                        a specific channel tuple like ('db_name', 'model_name', record_id),
                        or a string channel name).
        :param notification_type: A string identifying the type of notification
                                  (e.g., 'llm_chunk', 'progress_update').
        :param payload: The dictionary or other JSON-serializable data to send
                        as the message payload.
        :param user_id: The user ID to use when creating the bus message environment.
                        Defaults to SUPERUSER_ID to bypass potential permission issues
                        for the technical act of sending. Change if specific user
                        context is required for sending *and* permissions allow it.
        :return: True if the message was sent and committed successfully, False otherwise.
        """
        if not channel or not notification_type:
            _logger.warning("Cannot send immediate bus message: channel or notification_type missing.")
            return False

        try:
            with self.env.registry.cursor() as immediate_cr:
                immediate_env = api.Environment(immediate_cr, user_id, self.env.context)
                immediate_env['bus.bus']._sendone(channel, notification_type, payload)
                immediate_cr.commit()
                return True

        except Exception as e:
            _logger.error(
                "Failed to send immediate bus message (Channel: %s, Type: %s): %s",
                channel, notification_type, e, exc_info=True
            )
            immediate_cr.rollback()
            return False
