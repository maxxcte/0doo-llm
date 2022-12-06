/** @odoo-module **/

import { useRefToModel } from '@mail/component_hooks/use_ref_to_model';
import { registerMessagingComponent } from '@mail/utils/messaging_component';
const { Component, useRef, useState } = owl;

export class LLMChatThreadHeader extends Component {
    /**
     * @override
     */
    setup() {
        super.setup();
        useRefToModel({ fieldName: 'llmChatThreadNameInputRef', refName: 'threadNameInput' });
        
        // Local state for selected provider and model
        this.state = useState({
            selectedProviderId: this.thread.llmModel?.llmProvider?.id,
            selectedModelId: this.thread.llmModel?.id,
        });
    }

    get llmChatThreadHeaderView() {
        return this.props.record;
    }

    get threadView() {
        return this.llmChatThreadHeaderView.threadView;
    }

    get thread() {
        return this.threadView.thread;
    }

    get llmChat() {
        return this.thread.llmChat;
    }

    get llmProviders() {
        return this.llmChat.llmProviders;
    }

    get selectedProvider() {
        if (this.state.selectedProviderId) {
            return this.llmProviders.find(p => p.id === this.state.selectedProviderId);
        }
        return this.thread.llmModel?.llmProvider;
    }

    get selectedModel() {
        if (this.state.selectedModelId) {
            return this.filteredModels.find(m => m.id === this.state.selectedModelId);
        }
        return undefined;
    }
    get isSmall() {
        return this.messaging.device.isSmall;
    }
    get filteredModels() {
        if (!this.selectedProvider) {
            return this.llmChat.llmModels;
        }
        return this.llmChat.llmModels.filter(
            model => model.llmProvider?.id === this.selectedProvider.id
        );
    }

    /**
     * @param {Object} provider
     */
    onSelectProvider(provider) {
        // Update provider and clear model selection since it might not be compatible
        this.state.selectedProviderId = provider.id;
        this.state.selectedModelId = undefined;
        this.messaging.notify({
            title: 'Please select a model to save',
            message: 'Attention! Your model might not be compatible with the selected provider.',
            type: 'info',
        });
    }

    /**
     * @param {Object} model
     */
    async onSelectModel(model) {
        // Save both model and its provider to backend since they must be compatible
        await this.thread.updateLLMChatThreadSettings({
            llmModelId: model.id,
            llmProviderId: model.llmProvider.id,
        });
        // Update local state to match
        this.state.selectedProviderId = model.llmProvider.id;
        this.state.selectedModelId = model.id;
        this.messaging.notify({
            title: 'Model selected',
            message: 'Your model has been successfully updated for this thread.',
            type: 'success',
        });
    }

    /**
     * Toggle thread list visibility on mobile
     */
    _onToggleThreadList() {
        this.thread.llmChat.llmChatView.update({
            isThreadListVisible: !this.thread.llmChat.llmChatView.isThreadListVisible,
        });
    }

    /**
     * Handle keydown in thread name input
     * @param {KeyboardEvent} ev 
     */
    onKeyDownThreadNameInput(ev) {
        switch(ev.key) {
            case 'Enter':
                ev.preventDefault();
                this.llmChatThreadHeaderView.saveThreadName();
                break;
            case 'Escape':
                ev.preventDefault();
                this.llmChatThreadHeaderView.discardThreadNameEdition();
                break;
        }
    }

    /**
     * Handle input value change
     * @param {Event} ev 
     */
    onInputThreadNameInput(ev) {
        this.llmChatThreadHeaderView.update({ pendingName: ev.target.value });
    }
}

Object.assign(LLMChatThreadHeader, {
    props: { record: Object },
    template: 'llm_thread.LLMChatThreadHeader',
});

registerMessagingComponent(LLMChatThreadHeader);
