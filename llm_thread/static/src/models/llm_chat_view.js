/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { attr, one } from '@mail/model/model_field';

registerModel({
    name: 'LLMChatView',
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
});
