/** @odoo-module **/

import { registerMessagingComponent } from '@mail/utils/messaging_component';

const { Component } = owl;

export class LLMChatSidebar extends Component {
    /**
     * @returns {LLMChatView}
     */
    get llmChatView() {
        return this.props.record;
    }
}

Object.assign(LLMChatSidebar, {
    props: { record: Object },
    template: 'llm_thread.LLMChatSidebar',
});

registerMessagingComponent(LLMChatSidebar);
