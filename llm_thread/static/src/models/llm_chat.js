/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { attr, one, many } from '@mail/model/model_field';
import { clear } from '@mail/model/model_field_command';

registerModel({
    name: 'LLMChat',
    fields: {
        llmChatView: one('LLMChatView', {
            inverse: 'llmChat',
            isCausal: true,
        }),
        isInitThreadHandled: attr({
            default: false,
        }),
        activeThread: one('Thread', {
            inverse: 'llmChatAsActive',
        }),
        threads: many('Thread', {
            inverse: 'llmChat',
        }),
    },
    recordMethods: {
        async loadThreads() {
            const result = await this.env.services.rpc({
                model: 'llm.thread',
                method: 'search_read',
                args: [],
                kwargs: {
                    fields: ['name', 'state', 'last_message', 'message_ids', 'create_uid', 'create_date'],
                    order: 'create_date desc',
                },
            });
            
            // Convert results to Thread records
            const threadData = result.map(thread => ({
                id: thread.id,
                model: 'llm.thread',
                name: thread.name,
                messageCount: thread.message_ids ? thread.message_ids.length : 0,
                message_needaction_counter: 0, // We don't use needaction for LLM threads
                creator: thread.create_uid ? { id: thread.create_uid } : undefined,
                lastSeenByCurrentPartnerMessageId: thread.message_ids ? thread.message_ids[thread.message_ids.length - 1] : 0,
                isServerPinned: true, // Always pin LLM threads
            }));
            
            // Update threads in the store
            this.update({ threads: threadData });
            
            // Set active thread if none selected
            if (!this.activeThread && threadData.length > 0) {
                this.update({ activeThread: threadData[0] });
            }
        },
        
        close() {
            if (this.llmChatView) {
                this.llmChatView.update({ llmChat: clear() });
            }
        },
        
        /**
         * @param {integer} threadId 
         */
        async selectThread(threadId) {
            const thread = this.threads.find(t => t.id === threadId);
            if (thread) {
                this.update({ activeThread: thread });
                // Load thread messages if needed
                await thread.fetchData(['messages']);
            }
        },
    },
});
