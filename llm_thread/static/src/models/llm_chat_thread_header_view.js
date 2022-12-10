/** @odoo-module **/

import { registerModel } from '@mail/model/model_core';
import { attr, many, one } from '@mail/model/model_field';
import { clear } from '@mail/model/model_field_command';

registerModel({
    name: 'LLMChatThreadHeaderView',
    lifecycleHooks: {
        _created() {
            // Set initial values without triggering backend update
            this._initializeState();
        },
    },
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
        selectedProviderId: attr(),
        selectedModelId: attr(),
        _isInitializing: attr({
            default: false,
        }),
        selectedProvider: one('LLMProvider', {
            compute(){
                if(!this.selectedProviderId){
                    return clear();
                } else {
                    console.log(this.threadView.thread);
                    return this.threadView.thread.llmChat.llmProviders.find(p => p.id === this.selectedProviderId) || this.selectedModel?.llmProvider;
                }
            }
        }),
        selectedModel: one('LLMModel', {
            compute(){
                console.log("SelectedModelID",this.selectedModelId);
                if(!this.selectedModelId){
                    console.log("Clearning the selectedModelId");
                    return clear();
                } else {
                    return this.threadView.thread.llmChat.llmModels.find(m => m.id === this.selectedModelId);
                }
            }
        }),
        modelsAvailableToSelect: many('LLMModel', {
            compute(){
                if(!this.selectedProviderId){
                    return [];
                }
                return this.threadView.thread.llmChat?.llmModels?.filter(
                    model => model.llmProvider?.id === this.selectedProviderId
                ) || [];
            }
        }),
    },
    recordMethods: {
        /**
         * Initialize or reset state based on current thread
         * @private
         */
        _initializeState() {
            this.update({ 
                _isInitializing: true,
                selectedProviderId: this.threadView.thread.llmModel?.llmProvider?.id,
                selectedModelId: this.threadView.thread.llmModel?.id,
            });
        },

        /**
         * Handle thread changes
         * @private
         */
        _onThreadViewChange() {
            this._initializeState();
        },

        /**
         * Handle model changes
         * @private
         */
        async _onSelectedModelChange(){
            // Skip backend update during initialization
            if(!this.selectedModel || this._isInitializing){
                if(this._isInitializing){
                    this.update({ _isInitializing: false });
                    return;
                }
            }
            
            await this.threadView.thread.updateLLMChatThreadSettings({
                llmModelId: this.selectedModel.id,
                llmProviderId: this.selectedModel.llmProvider.id,
            });
        },

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
    },
    onChanges: [
        {
            dependencies: ['selectedModel'],
            methodName: '_onSelectedModelChange',
        },
        {
            dependencies: ['threadView.thread.llmChat.activeThread'],
            methodName: '_onThreadViewChange',
        },
    ],
});
