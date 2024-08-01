/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { clear } from '@mail/model/model_field_command';

registerPatch({
    name: 'MessagingNotificationHandler',
    recordMethods: {
        
        /**
         * @override
         * @private
         * @param {Object} message
         */
        _handleNotification(message) {
            if (message.type === 'llm.thread/delete') {
                return this._handleLLMThreadDelete(message);
            }
            super._handleNotification(message);
        },
        
        /**
         * @private
         * @param {Object} message
         */
        _handleLLMThreadDelete(message) {
            const thread = this.messaging.models.Thread.findFromIdentifyingData({ id: message.payload.id, model: "llm.thread" });
            console.log('Received thread delete event for ID:', message.payload.id, 'Found thread:', thread);

            if (thread) {
                const llmChat = thread.llmChat;
                console.log('Associated llmChat:', llmChat);

                if (llmChat) {
                    const isActiveThread = llmChat.activeThread && llmChat.activeThread.id === thread.id;

                    // If the deleted thread was the active one, check for and stop any active stream
                    if (isActiveThread) {
                        const composer = llmChat.llmChatView?.composer;
                        if (composer && composer.isStreaming) {
                             console.log('Deleted thread was active and composer is streaming. Closing EventSource.');
                             composer._closeEventSource(); // Use the existing method from composer.js
                        }
                    }

                    const updatedData = {
                        threads: llmChat.threads.filter(t => t.id !== thread.id),
                    };

                    if (isActiveThread) {
                        console.log('Deleted thread was the active thread. Clearing activeThread.');
                        updatedData.activeThread = clear();
                    } else {
                         console.log('Deleted thread was not the active thread. Active thread remains:', llmChat.activeThread);
                    }

                    llmChat.update(updatedData);
                    console.log('llmChat after update:', llmChat);
                } else {
                     console.log('No associated llmChat found for the deleted thread.');
                }

                console.log('Deleting thread model instance:', thread);
                thread.delete();

            } else {
                 console.log('Thread with ID', message.payload.id, 'not found in frontend models.');
            }
        },
    },
});
