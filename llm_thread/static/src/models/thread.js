/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { one } from '@mail/model/model_field';

registerPatch({
    name: 'Thread',
    fields: {
        llmChat: one('LLMChat', {
            inverse: 'threads',
        }),
        activeLLMChat: one('LLMChat', {
            inverse: 'activeThread',
        }),
    },
});
