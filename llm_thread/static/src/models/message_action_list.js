/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { one } from '@mail/model/model_field'; 
import { _t } from "@web/core/l10n/translation";
import { clear } from '@mail/model/model_field_command';

// 1. Patch MessageActionList to add compute fields for our custom actions
registerPatch({
    name: 'MessageActionList',
    fields: {
        actionThumbUp: one('MessageAction', {
            compute() {
                // Show thumb up only for assistant messages
                if (this.message && !this.message.author) {
                    return {};
                }
                return clear();
            },
            inverse: 'messageActionListOwnerAsThumbUp',
        }),
        actionThumbDown: one('MessageAction', {
            compute() {
                // Show thumb down only for assistant messages
                if (this.message && !this.message.author) {
                    return {};
                }
                return clear();
            },
            inverse: 'messageActionListOwnerAsThumbDown',
        }),
    },
});