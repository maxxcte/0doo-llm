/** @odoo-module **/

import { useModels } from '@mail/component_hooks/use_models';
import { registerMessagingComponent } from '@mail/utils/messaging_component';

const { Component, useState } = owl;

export class LLMChatThreadList extends Component {
    setup() {
        useModels();
        super.setup();
        
        this.state = useState({
            isLoading: false,
        });
    }
    
    /**
     * @returns {LLMChatView}
     */
    get llmChatView() {
        return this.props.record;
    }
    
    /**
     * Handle thread click
     * @param {Thread} thread 
     */
    async _onThreadClick(thread) {
        if (this.state.isLoading) return;
        
        this.state.isLoading = true;
        try {
            await this.llmChatView.llmChat.selectThread(thread.id);
        } catch (error) {
            this.env.services.notification.notify({
                title: 'Error',
                message: 'Failed to load thread',
                type: 'danger',
            });
        } finally {
            this.state.isLoading = false;
        }
    }
}

Object.assign(LLMChatThreadList, {
    props: { record: Object },
    template: 'llm_thread.LLMChatThreadList',
});

registerMessagingComponent(LLMChatThreadList);
