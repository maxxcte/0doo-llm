/** @odoo-module **/

import { registerMessagingComponent } from '@mail/utils/messaging_component';
import { useComponentToModel } from '@mail/component_hooks/use_component_to_model';
const { Component } = owl;

export class LLMChatComposer extends Component {
    /**
     * @override
     */
    setup() {
        super.setup();
        useComponentToModel({ fieldName: 'component' });
    }
    /**
     * @returns {ComposerView}
     */
    get composerView() {
        return this.props.record;
    }

    /**
     * @returns {boolean}
     */
    get isDisabled() {
        return !this.composerView.composer.canPostMessage;
    }

    //--------------------------------------------------------------------------
    // Private
    //--------------------------------------------------------------------------

    /**
     * Intercept send button click
     * @private
     */
    async _onClickSend() {
        if (this.isDisabled) {
            return;
        }
        
        // Pre-process before sending
        const content = this.composerView.composer.textInputContent;
        console.log('Sending message:', content);
        
        // Here we can add logic to handle the message before sending
        // For example, we might want to:
        // 1. Store the message for LLM processing
        // 2. Update UI to show "thinking" state
        // 3. Trigger LLM processing
        
        // Call original send handler
        await this.composerView.sendMessage();
        this.composerView.update({
            doFocus: true,
        });
        console.log('Message sent');
    }
}

Object.assign(LLMChatComposer, {
    props: { record: Object },
    template: 'llm_thread.LLMChatComposer',
});

registerMessagingComponent(LLMChatComposer);