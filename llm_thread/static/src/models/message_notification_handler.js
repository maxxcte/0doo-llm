/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';

const STREAM_START_NOTIFICATION = 'mail.message/stream_start';
const STREAM_CHUNK_NOTIFICATION = 'mail.message/stream_chunk';
const STREAM_DONE_NOTIFICATION = 'mail.message/stream_done';

registerPatch({
    name: 'MessagingNotificationHandler',

    recordMethods: {
        /**
         * Handles notifications that were not processed by the core _handleNotifications switch statement.
         * This is the designated extension point for custom notification types.
         * @override
         * @param {Object} notification The notification object from the bus.
         * @param {string} notification.type The notification type (e.g., 'mail.message/stream_start').
         * @param {Object} notification.payload The data payload.
         */
        _handleNotification(notification) {
            if (!this.messaging || !this.messaging.exists()) {
                return this._super(notification);
            }

            if (!notification.payload) {
                 return this._super(notification);
            }

            try {
                if (notification.type === 'mail.message/insert_custom'){
                    const message = this.messaging.models.Message.insert(
                        this.messaging.models.Message.convertData(notification.payload)
                    );
                    return;
                }
                else if (notification.type === 'mail.message/update_custom') {
                    const message = this.messaging.models['Message'].findFromIdentifyingData({ id: notification.payload.id });
                    if (message) {
                        message.update(this.messaging.models.Message.convertData(notification.payload));
                    }
                    return;
                }
                else if (notification.type === 'llm.thread/update_state') {
                    const thread = this.messaging.models['Thread'].findFromIdentifyingData({ id: notification.payload.id, model: 'llm.thread' });
                    if (thread) {
                        thread.update({ state: notification.payload.state });
                    }
                    return;
                }
                else {
                    return this._super(notification);
                }
            } catch (error) {
                 console.error(`Error handling custom notification ${notification.type} for message ${notification.payload?.message_id}:`, error, notification.payload);
                 return this._super(notification);
            }
        },
    },
});