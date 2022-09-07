/** @odoo-module **/

import { useModels } from '@mail/component_hooks/use_models';
import { registerMessagingComponent } from '@mail/utils/messaging_component';

const { Component } = owl;

export class LLMChatThreadList extends Component {
    /**
     * @override
     */
    setup() {
        useModels();
        super.setup();
    }

    /**
     * @returns {LLMChat}
     */
    get llmChat() {
        return this.messaging.llmChat;
    }

    /**
     * @returns {Thread[]}
     */
    get threads() {
        if (!this.llmChat) {
            return [];
        }
        return this.llmChat.threads;
    }

    /**
     * @param {MouseEvent} ev
     * @param {Thread} thread
     */
    onClickThread(ev, thread) {
        this.llmChat.selectThread(thread.id);
    }
}

Object.assign(LLMChatThreadList, {
    template: 'llm_thread.LLMChatThreadList',
});

registerMessagingComponent(LLMChatThreadList);
