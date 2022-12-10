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

    get llmModels() {
        return this.llmChat.llmModels;
    }

    get isSmall() {
        return this.messaging.device.isSmall;
    }

    /**
     * @param {Object} provider
     */
    onSelectProvider(provider) {
        // Update provider and clear model selection since it might not be compatible
        this.llmChatThreadHeaderView.update({
            selectedProviderId: provider.id,
            selectedModelId: undefined,
        });
        this.messaging.notify({
            title: 'Please select a model to save',
            message: 'Attention! Your model might not be compatible with the selected provider.',
            type: 'info',
        });
    }

    /**
     * @param {Object} model
     */
    onSelectModel(model) {
        // Just update the selectedModelId, the onChange handler will take care of the rest
        this.llmChatThreadHeaderView.update({
            selectedModelId: model.id,
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
