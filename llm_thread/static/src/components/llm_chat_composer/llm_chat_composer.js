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
        
        await this.composerView.sendMessage();
        this.composerView.update({
            doFocus: true,
        });
        this.composerView.startStreaming();
    }
}

Object.assign(LLMChatComposer, {
    props: { record: Object },
    template: 'llm_thread.LLMChatComposer',
});

registerMessagingComponent(LLMChatComposer);