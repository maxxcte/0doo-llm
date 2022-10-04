/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { one } from '@mail/model/model_field';
import { clear } from '@mail/model/model_field_command';


registerPatch({
    name: 'ThreadView',
    recordMethods: {
        /**
        * Opens the thread form view for editing
        */
        async openThreadSettings() {
            await this.env.services.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'llm.thread',
                res_id: this.thread.id,
                views: [[false, 'form']],
                target: 'new',
                flags: {
                    mode: 'edit'
                }
            }, {
                onClose: () => {
                    // Reload thread data when form is closed
                    this.thread.llmChat.loadThreads();
                }
            });
        },
    }
});
