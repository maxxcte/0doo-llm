/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { attr, one, many } from '@mail/model/model_field';

registerModel({
    name: 'LLMModel',
    fields: {
        id: attr({
            identifying: true,
        }),
        name: attr({
            required: true,
        }),
        llmProvider: one('LLMProvider', {
            inverse: 'llmModels',
        }),
        threads: many('Thread', {
            inverse: 'llmModel',
        }),
        default: attr({
            default: false,
        }),
    },
});