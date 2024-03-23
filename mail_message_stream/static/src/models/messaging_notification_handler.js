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
                console.warn(`Ignoring notification type ${notification.type} due to missing payload.`);
                return this._super(notification);
            }

            const messageModel = notification.payload.message_id
                ? this.messaging.models['Message'].findFromIdentifyingData({ id: notification.payload.message_id })
                : undefined;

            try {
                switch (notification.type) {
                    case STREAM_START_NOTIFICATION:
                        if (messageModel && messageModel.exists()) {
                            messageModel.handleStreamStart(notification.payload);
                        } else {
                            console.debug(`Stream start event received for message ${notification.payload.message_id}, but message model not found locally.`);
                        }
                        return;

                    case STREAM_CHUNK_NOTIFICATION:
                        if (messageModel && messageModel.exists()) {
                            messageModel.handleStreamChunk(notification.payload);
                        } else {
                            console.debug(`Stream chunk event received for message ${notification.payload.message_id}, but message model not found locally.`);
                        }
                        return;

                    case STREAM_DONE_NOTIFICATION:
                        if (messageModel && messageModel.exists()) {
                            messageModel.handleStreamDone(notification.payload);
                        } else {
                            console.debug(`Stream done event received for message ${notification.payload.message_id}, but message model not found locally.`);
                        }
                        return;

                    default:
                        return this._super(notification);
                }
            } catch (error) {
                 console.error(`Error handling custom notification ${notification.type} for message ${notification.payload?.message_id}:`, error, notification.payload);
                 return this._super(notification);
            }
        },
    },
});