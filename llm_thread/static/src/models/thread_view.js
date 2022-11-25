/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { one } from '@mail/model/model_field';
import { attr } from '@mail/model/model_field';
import { clear } from '@mail/model/model_field_command';

registerPatch({
    name: 'ThreadView',
    fields: {
        isEditingName: attr({
            default: false,
        }),
        pendingName: attr({
            default: '',
        }),
    },
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

        /**
         * Start editing thread name
         */
        onClickTopbarThreadName() {
            if (this.isEditingName) {
                return;
            }
            this.update({
                isEditingName: true,
                pendingName: this.thread.name,
            });
        },

        /**
         * Save thread name changes to server
         */
        async saveThreadName() {
            if (!this.pendingName.trim()) {
                this.discardThreadNameEdition();
                return;
            }
            
            const newName = this.pendingName.trim();
            if (newName === this.thread.name) {
                this.discardThreadNameEdition();
                return;
            }

            try {
                await this.env.services.rpc({
                    model: 'llm.thread',
                    method: 'write',
                    args: [[this.thread.id], { name: newName }],
                });
                await this.thread.llmChat.loadThreads();
                this.update({
                    isEditingName: false,
                    pendingName: '',
                });
            } catch (error) {
                this.env.services.notification.notify({
                    message: this.env._t("Failed to update thread name"),
                    type: 'danger',
                });
                this.discardThreadNameEdition();
            }
        },

        /**
         * Discard thread name changes
         */
        discardThreadNameEdition() {
            this.update({
                isEditingName: false,
                pendingName: '',
            });
        },
    }
});
