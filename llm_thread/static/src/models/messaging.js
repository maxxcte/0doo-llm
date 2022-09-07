/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { one } from '@mail/model/model_field';

registerPatch({
    name: 'Messaging',
    fields: {
        llmChat: one('LLMChat', {
            default: {},
            isCausal: true,
        }),
    },
});
