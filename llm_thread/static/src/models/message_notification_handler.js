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
                return this._handleLLMThreadsDelete(message);
            }
            super._handleNotification(message);
        },

        _handleLLMThreadsDelete(message) {
            console.log('message', message);
            const ids = message.payload.ids;
            for (const id of ids) {
                this._handleLLMThreadDelete(id);
            }
        },
        
        /**
         * @private
         * @param {Object} message
         */
        _handleLLMThreadDelete(id) {
            const thread = this.messaging.models.Thread.findFromIdentifyingData({ id, model: "llm.thread" });
            if (thread) {
                const llmChat = thread.llmChat;
                if (llmChat) {
                    const isActiveThread = llmChat.activeThread && llmChat.activeThread.id === thread.id;
                    if (isActiveThread) {
                        const composer = llmChat.llmChatView?.composer;
                        if (composer && composer.isStreaming) {
                            composer._closeEventSource();
                        }
                    }
                    const updatedData = {
                        threads: llmChat.threads.filter(t => t.id !== thread.id),
                    };
                    if (isActiveThread) {
                        updatedData.activeThread = clear();
                    }
                    llmChat.update(updatedData);
                }
                thread.delete();
            }
        },
    },
});
