/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { attr, one } from '@mail/model/model_field';
import { clear } from '@mail/model/model_field_command';

registerModel({
    name: 'LLMChatView',
    recordMethods: {
        /**
         * @private
         */
        _onLLMChatActiveThreadChanged() {
            this.env.services.router.pushState({
                action: this.llmChat.llmChatView.actionId,
                active_id: this.llmChat.activeId,
            });
        },
    },
    fields: {
        actionId: attr(),
        llmChat: one('LLMChat', {
            inverse: 'llmChatView',
            required: true,
        }),
        isActive: attr({
            compute() {
                return Boolean(this.llmChat);
            },
        }),
        threadViewer: one('ThreadViewer', {
            compute() {
                if (!this.llmChat.activeThread) {
                    return clear();
                }
                return {
                    hasThreadView: true,
                    thread: this.llmChat.activeThread,
                    threadCache: this.llmChat.threadCache,
                };
            },
        }),
        threadView: one('ThreadView', {
            compute() {
                if (!this.threadViewer) {
                    return clear();
                }
                return {
                    threadViewer: this.threadViewer,
                    messageListView: {}, // This is crucial - we create MessageListView here
                };
            },
        }),
        composer: one('Composer', {
            compute() {
                if (!this.threadViewer) {
                    return clear();
                }
                return { thread: this.threadViewer.thread };
            },
        }),
    },
    onChanges: [
        {
            dependencies: ['llmChat.activeThread'],
            methodName: '_onLLMChatActiveThreadChanged',
        },
    ],
});
