/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { attr, one, many } from '@mail/model/model_field';
import { clear } from '@mail/model/model_field_command';

registerModel({
    name: 'LLMChat',
    recordMethods: {
        /**
         * @param {Thread} thread
         * @returns {string}
         */
        threadToActiveId(thread) {
            return `${thread.model}_${thread.id}`;
        },
        async loadThreads() {
            const result = await this.messaging.rpc({
                model: 'llm.thread',
                method: 'search_read',
                kwargs: {
                    domain: [], // Empty domain to fetch all threads
                    fields: ['name', 'message_ids', 'create_uid', 'create_date'],
                    order: 'create_date desc',
                },
            });
            
            // Convert results to Thread records
            const threadData = result.map(thread => ({
                id: thread.id,
                model: 'llm.thread',
                name: thread.name,
                message_needaction_counter: 0, // We don't use needaction for LLM threads
                creator: thread.create_uid ? { id: thread.create_uid } : undefined,
                isServerPinned: true, // Always pin LLM threads
            }));
            
            // Update threads in the store
            this.update({ threads: threadData });
            console.log('threadData', this.threads);
            
            // Set active thread if none selected
            if (!this.activeThread && threadData.length > 0) {
                this.update({ activeThread: threadData[0] });
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
    fields: {
        activeId: attr({
            compute() {
                if (!this.activeThread) {
                    return clear();
                }
                return this.threadToActiveId(this.activeThread);
            },
        }),
        llmChatView: one('LLMChatView', {
            inverse: 'llmChat',
            isCausal: true,
        }),
        isInitThreadHandled: attr({
            default: false,
        }),
        activeThread: one('Thread', {
            inverse: 'activeLLMChat',
        }),
        threads: many('Thread', {
            inverse: 'llmChat',
        }),
    },
});
