/** @odoo-module **/

import { Component } from "@odoo/owl";
import { registerMessagingComponent } from '@mail/utils/messaging_component';

export class LLMChatThreadHeader extends Component {
    /**
     * Opens thread settings to modify provider/model
     */
    async onSettingsClick() {
        await this.threadView.openThreadSettings();
    }

    get threadView(){
        return this.props.record;
    }

    get thread(){
        return this.threadView.thread;
    }
    /**
     * Get the model name if available
     */
    get modelName() {
        return this.llmModel?.name;
    }

    get providerName(){
        return this.llmModel?.llmProvider?.name;
    }

    get llmModel(){
        return this.thread?.llmModel;
    }
}

Object.assign(LLMChatThreadHeader, {
    props: { record: Object },
    template: 'llm_thread.LLMChatThreadHeader',
});

registerMessagingComponent(LLMChatThreadHeader);
