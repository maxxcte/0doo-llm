/** @odoo-module **/

import { useModels } from '@mail/component_hooks/use_models';
import { registerMessagingComponent } from '@mail/utils/messaging_component';

const { Component, useState, onWillStart } = owl;

export class LLMChatThread extends Component {
    setup() {
        useModels();
        super.setup();
        
        this.state = useState({
            newMessage: '',
            isLoading: true,
            isSending: false,
        });
        
        onWillStart(async () => {
            await this._loadMessages();
        });
    }
    
    /**
     * @returns {Thread}
     */
    get thread() {
        return this.props.record;
    }
    
    /**
     * @returns {Message[]}
     */
    get messages() {
        return this.thread.messages || [];
    }
    
    /**
     * Load messages for the thread
     */
    async _loadMessages() {
        this.state.isLoading = true;
        try {
            await this.thread.fetchData(['messages']);
        } catch (error) {
            this.env.services.notification.notify({
                title: 'Error',
                message: 'Failed to load messages',
                type: 'danger',
            });
        } finally {
            this.state.isLoading = false;
        }
    }
    
    /**
     * Handle message input change
     * @param {Event} ev 
     */
    _onInputChange(ev) {
        this.state.newMessage = ev.target.value;
    }
    
    /**
     * Handle message send
     * @param {Event} ev 
     */
    async _onSend(ev) {
        if (ev.key === 'Enter' && !ev.shiftKey) {
            ev.preventDefault();
            if (!this.state.newMessage.trim() || this.state.isSending) {
                return;
            }
            
            this.state.isSending = true;
            try {
                // Send message using RPC
                await this.messaging.rpc({
                    model: 'llm.thread',
                    method: 'send_message',
                    args: [[this.thread.id], this.state.newMessage],
                });
                
                // Clear input
                this.state.newMessage = '';
                
                // Reload messages
                await this._loadMessages();
            } catch (error) {
                this.env.services.notification.notify({
                    title: 'Error',
                    message: 'Failed to send message',
                    type: 'danger',
                });
            } finally {
                this.state.isSending = false;
            }
        }
    }
}

Object.assign(LLMChatThread, {
    props: {
        record: Object,
    },
    template: 'llm_thread.LLMChatThread',
});

registerMessagingComponent(LLMChatThread);
