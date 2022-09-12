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
     * @returns {LLMChat}
     */
    get llmChat() {
        return this.messaging.llmChat;
    }
    
    /**
     * @returns {Thread[]}
     */
    get threads() {
        return this.llmChat.threads || [];
    }
    
    /**
     * @returns {Thread}
     */
    get activeThread() {
        return this.llmChat.activeThread;
    }
    
    /**
     * Handle thread click
     * @param {Thread} thread 
     */
    async _onThreadClick(thread) {
        if (this.state.isLoading) return;
        
        this.state.isLoading = true;
        try {
            await this.llmChat.selectThread(thread.id);
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
    
    /**
     * Create a new thread
     */
    async _onNewThread() {
        if (this.state.isLoading) return;
        
        this.state.isLoading = true;
        try {
            // Create new thread
            const thread = await this.messaging.rpc({
                model: 'llm.thread',
                method: 'create',
                args: [{ name: 'New Chat' }],
            });
            
            // Reload threads and select the new one
            await this.llmChat.loadThreads();
            await this.llmChat.selectThread(thread);
        } catch (error) {
            this.env.services.notification.notify({
                title: 'Error',
                message: 'Failed to create new thread',
                type: 'danger',
            });
        } finally {
            this.state.isLoading = false;
        }
    }
}

Object.assign(LLMChatThreadList, {
    template: 'llm_thread.LLMChatThreadList',
});

registerMessagingComponent(LLMChatThreadList);
