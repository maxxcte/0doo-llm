/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { attr, one } from '@mail/model/model_field';

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
    },
    onChanges: [
        {
            dependencies: ['llmChat.activeThread'],
            methodName: '_onLLMChatActiveThreadChanged',
        },
    ],
});
