/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { one } from '@mail/model/model_field';
import { attr } from '@mail/model/model_field';

registerModel({
    name: 'LLMChatThreadHeaderView',
    fields: {
        threadView: one('ThreadView', {
            inverse: 'llmChatThreadHeaderView',
        }),
        isEditingName: attr({
            default: false,
        }),
        pendingName: attr({
            default: '',
        }),
        llmChatThreadNameInputRef: attr(),
    },
    recordMethods: {
        /**
         * Opens the thread form view for editing
         */
        async openThreadSettings() {
            await this.env.services.action.doAction({
                type: 'ir.actions.act_window',
                res_model: 'llm.thread',
                res_id: this.threadView.thread.id,
                views: [[false, 'form']],
                target: 'new',
                flags: {
                    mode: 'edit'
                }
            }, {
                onClose: () => {
                    // Reload thread data when form is closed
                    this.threadView.thread.llmChat.loadThreads();
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
                pendingName: this.threadView.thread.name,
            });
        },

        /**
         * Save thread name changes to server
         */
        async saveThreadName() {
            const thread = this.threadView.thread;
            if (!this.pendingName.trim()) {
                this.discardThreadNameEdition();
                return;
            }
            
            const newName = this.pendingName.trim();
            if (newName === thread.name) {
                this.discardThreadNameEdition();
                return;
            }

            try {
                await thread.updateLLMChatThreadSettings({name: newName});
                await thread.llmChat.loadThreads();
                this.update({
                    isEditingName: false,
                    pendingName: '',
                });
            } catch (error) {
                console.error('Error updating thread name:', error);
                this.messaging.notify({
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
