/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { one } from '@mail/model/model_field';
import { clear } from '@mail/model/model_field_command';


registerPatch({
    name: 'Thread',
    fields: {
        llmChat: one('LLMChat', {
            inverse: 'threads',
        }),
        activeLLMChat: one('LLMChat', {
            inverse: 'activeThread',
        }),
        llm_model: one('LLMModel', {
            inverse: 'threads',
        }),
    },
});
