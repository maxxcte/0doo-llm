/** @odoo-module **/

import { useRefToModel } from '@mail/component_hooks/use_ref_to_model';
import { registerMessagingComponent } from '@mail/utils/messaging_component';
const { Component } = owl;

export class LLMChatThreadHeader extends Component {
    setup() {
        super.setup();
        useRefToModel({ fieldName: 'threadNameInputRef', refName: 'threadNameInput' });
    }

    get threadView() {
        return this.props.record;
    }

    get thread() {
        return this.threadView.thread;
    }

    get modelName() {
        return this.llmModel?.name;
    }

    get providerName() {
        return this.llmModel?.llmProvider?.name;
    }

    get llmModel() {
        return this.thread?.llmModel;
    }

    get isSmall() {
        return this.messaging.device.isSmall;
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
                this.threadView.saveThreadName();
                break;
            case 'Escape':
                ev.preventDefault();
                this.threadView.discardThreadNameEdition();
                break;
        }
    }

    /**
     * Handle input value change
     * @param {Event} ev 
     */
    onInputThreadNameInput(ev) {
        this.threadView.update({ pendingName: ev.target.value });
    }
}

Object.assign(LLMChatThreadHeader, {
    props: { record: Object },
    template: 'llm_thread.LLMChatThreadHeader',
});

registerMessagingComponent(LLMChatThreadHeader);
