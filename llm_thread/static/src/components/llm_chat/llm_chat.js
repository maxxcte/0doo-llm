/** @odoo-module **/

import { useModels } from '@mail/component_hooks/use_models';
import { registerMessagingComponent } from '@mail/utils/messaging_component';
import { getMessagingComponent } from '@mail/utils/messaging_component';

// Import thread list component
import '@llm_thread/components/llm_chat_thread_list/llm_chat_thread_list';

const { Component, onWillDestroy } = owl;

export class LLMChat extends Component {
    /**
     * @override
     */
    setup() {
        useModels();
        super.setup();
        onWillDestroy(() => this._willDestroy());
        
        this.env.services.messaging.modelManager.messagingCreatedPromise.then(async () => {
            const { action } = this.props;
            const initThreadId = action.params && action.params.default_thread_id;
            
            // Create LLMChat if it doesn't exist
            if (!this.messaging.llmChat) {
                this.messaging.update({
                    llmChat: {}
                });
            }
            this.llmChat = this.messaging.llmChat;
            
            // Create LLMChatView and link it to LLMChat
            this.llmChat.update({
                llmChatView: {
                    actionId: action.id,
                }
            });
            
            // Wait for messaging to be initialized
            await this.messaging.initializedPromise;
            
            if (!this.llmChat.isInitThreadHandled) {
                this.llmChat.update({ isInitThreadHandled: true });
                await this.llmChat.loadThreads();
                
                if (initThreadId) {
                    await this.llmChat.selectThread(initThreadId);
                }
            }
        });
        
        // Handle multiple instances like DiscussContainer
        LLMChat.currentInstance = this;
    }

    /**
     * @returns {Messaging}
     */
    get messaging() {
        return this.env.services.messaging.modelManager.messaging;
    }

    /**
     * Handle cleanup when component is destroyed
     */
    _willDestroy() {
        if (LLMChat.currentInstance === this) {
            // Just remove the reference, don't try to clear required fields
            LLMChat.currentInstance = null;
        }
    }
}

Object.assign(LLMChat, {
    props: {
        action: Object,
        actionId: { type: Number, optional: 1 },
        className: String,
        globalState: { type: Object, optional: 1 },
    },
    components: { 
        LLMChatThreadList: getMessagingComponent('LLMChatThreadList'),
    },
    template: 'llm_thread.LLMChat',
});

registerMessagingComponent(LLMChat);
