/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { attr, one, many } from '@mail/model/model_field';
import { clear } from '@mail/model/model_field_command';

registerModel({
    name: 'LLMChat',
    recordMethods: {
        /**
         * Close the LLM chat. Should reset its internal state.
         */
        close() {
            this.update({ llmChatView: clear() });
        },

        /**
         * Opens thread from init active id if the thread exists.
         */
        openInitThread() {
            const [model, id] = typeof this.initActiveId === 'number'
                ? ['llm.thread', this.initActiveId]
                : this.initActiveId.split('_');
            const thread = this.messaging.models['Thread'].findFromIdentifyingData({
                id: Number(id),
                model,
            });
            if (!thread) {
                return;
            }
            this.selectThread(thread.id);
        },

        /**
         * Opens the given thread in LLMChat
         *
         * @param {Thread} thread
         */
        async openThread(thread) {
            this.update({ thread });
            if (!this.llmChatView) {
                this.env.services.action.doAction(
                    'llm_thread.action_llm_chat',
                    {
                        name: this.env._t("Chat"),
                        active_id: this.threadToActiveId(thread),
                        clearBreadcrumbs: false,
                    },
                );
            }
        },

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
                    domain: [],
                    fields: ['name', 'message_ids', 'create_uid', 'create_date'],
                    order: 'create_date desc',
                },
            });
            
            // Convert results to Thread records
            const threadData = result.map(thread => ({
                id: thread.id,
                model: 'llm.thread',
                name: thread.name,
                message_needaction_counter: 0,
                creator: thread.create_uid ? { id: thread.create_uid } : undefined,
                isServerPinned: true,
            }));
            
            // Update threads in the store
            this.update({ threads: threadData });
            
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
                await thread.fetchData(['messages']);
            }
        },
        open() {
            this.update({ llmChatView: {} });
        },
    },
    fields: {
        /**
         * Formatted active id of the current thread
         */
        activeId: attr({
            compute() {
                if (!this.activeThread) {
                    return clear();
                }
                return this.threadToActiveId(this.activeThread);
            },
        }),
        /**
         * View component for this LLMChat
         */
        llmChatView: one('LLMChatView', {
            inverse: 'llmChat',
            isCausal: true,
        }),
        /**
         * Determines if the logic for opening a thread via the `initActiveId`
         * has been processed.
         */
        isInitThreadHandled: attr({
            default: false,
        }),
        /**
         * Formatted init thread on opening chat for the first time
         * Format: <threadModel>_<threadId>
         */
        initActiveId: attr({
            default: null,
        }),
        /**
         * Currently active thread
         */
        activeThread: one('Thread', {
            inverse: 'activeLLMChat',
        }),
        /**
         * All threads in this chat
         */
        threads: many('Thread', {
            inverse: 'llmChat',
        }),
    },
});