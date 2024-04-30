/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { attr } from "@mail/model/model_field";
import { clear } from '@mail/model/model_field_command';

registerPatch({
    name: 'Message',
    fields: {
        /**
         * Indicates if content for this message is currently being streamed
         * via the mail_message_stream bus events.
         */
        isStreaming: attr({ default: false }),
        /**
         * Holds the unique identifier for the currently active stream associated
         * with this message instance. Used to correlate chunk/done events.
         */
        activeStreamId: attr({ default: false }),
        /**
         * Holds accumulated text chunks or other temporary display data received
         * during an active stream. The specific rendering depends on the consumer module.
         */
        streamingContent: attr({ default: '' }),
        /**
         * Stores the 'initial_data' received from the stream_start event payload.
         * This can be used by consuming modules to render placeholders or context
         * before chunks arrive (e.g., tool definition).
         */
        initialStreamData: attr({ default: false }),
        /**
         * Stores an error message string if the stream associated with this
         * message ended with an error, received from the stream_done event.
         */
        streamError: attr({ default: false }),
    },
    recordMethods: {
        /**
         * Handles the 'mail.message/stream_start' notification payload.
         * Updates the message's state to reflect that streaming has begun.
         * Called by the patched MessagingNotificationHandler.
         *
         * @param {Object} payload The full payload from the bus notification.
         * @param {integer} payload.message_id
         * @param {Object} payload.data Contains stream-specific data.
         * @param {string} payload.data.stream_id The unique ID for this stream.
         * @param {Object} [payload.data.initial_data] Optional initial context.
         */
        handleStreamStart(payload) {
            this.update({
                isStreaming: true,
                activeStreamId: payload?.data?.stream_id,
                initialStreamData: payload?.data?.initial_data,
                streamingContent: '',
                streamError: false,
            });
        },

        /**
         * Handles the 'mail.message/stream_chunk' notification payload.
         * Updates the streaming content if the stream_id matches the active one.
         * Called by the patched MessagingNotificationHandler.
         *
         * @param {Object} payload The full payload from the bus notification.
         * @param {integer} payload.message_id
         * @param {Object} payload.data Contains stream-specific data.
         * @param {string} payload.data.stream_id The unique ID for this stream.
         * @param {any} payload.data.chunk The data chunk.
         */
        handleStreamChunk(payload) {
            if (this.isStreaming && this.activeStreamId === payload?.data?.stream_id && payload?.data?.chunk !== undefined) {
                this.update({ streamingContent: this.streamingContent + payload.data.chunk });
            } else if (this.activeStreamId !== payload?.data?.stream_id) {
                 console.warn(`Ignoring chunk for Msg ${this.id} - Stream ID mismatch. Expected: ${this.activeStreamId}, Got: ${payload?.data?.stream_id}`);
            }
        },

        /**
         * Handles the 'mail.message/stream_done' notification payload.
         * Updates the message's state to reflect stream completion or error.
         * Called by the patched MessagingNotificationHandler.
         *
         * @param {Object} payload The full payload from the bus notification.
         * @param {integer} payload.message_id
         * @param {Object} payload.data Contains stream-specific data.
         * @param {string} payload.data.stream_id The unique ID for this stream.
         * @param {Object} [payload.data.final_data] Optional final data (e.g., full message).
         * @param {string} [payload.data.error] Optional error message.
         */
        handleStreamDone(payload) {
            if (this.activeStreamId === payload?.data?.stream_id) {
                const updateData = {
                    isStreaming: false,
                    streamError: payload?.data?.error,
                    activeStreamId: false,
                };
                this.update(updateData);
            } else if (payload?.data?.stream_id) {
                 console.warn(`Ignoring done for Msg ${this.id} - Stream ID mismatch. Expected: ${this.activeStreamId}, Got: ${payload?.data?.stream_id}`);
            }
        },
    },
});