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
                // Reverted condition based on last successful state - show for assistant messages
                if (this.message) {
                    return {};
                }
                return clear();
            },
            inverse: 'messageActionListOwnerAsThumbUp',
        }),
        actionThumbDown: one('MessageAction', {
            compute() {
                // Reverted condition based on last successful state - show for assistant messages
                 if (this.message) {
                    return {};
                }
                return clear();
            },
            inverse: 'messageActionListOwnerAsThumbDown',
        }),
    },
});