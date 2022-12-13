/** @odoo-module **/

import { useModels } from '@mail/component_hooks/use_models';
import { registerMessagingComponent } from '@mail/utils/messaging_component';
const { Component } = owl;

export class LLMChatSidebar extends Component {
    setup() {
        useModels();
        super.setup();
    }

    /**
     * @returns {LLMChatView}
     */
    get llmChatView() {
        return this.props.record;
    }

    /**
     * Handle backdrop click to close sidebar on mobile
     */
    _onBackdropClick() {
        if (this.messaging.device.isSmall) {
            this.llmChatView.update({ isThreadListVisible: false });
        }
    }

    /**
     * Handle click on New Chat button
     */
    async _onClickNewChat() {
        const llmChat = this.llmChatView.llmChat;
        // Get the default model or first available model
        const defaultModel = llmChat.llmModels[0];
        if (!defaultModel) {
            return;
        }
        const threadName = `New Chat ${new Date().toLocaleString()}`;
        // Create new thread via RPC
        const threadId = await this.messaging.rpc({
            model: 'llm.thread',
            method: 'create',
            args: [[{
                model_id: defaultModel.id,
                provider_id: defaultModel.llmProvider.id,
                name: threadName,
            }]],
        });

        const threadDetails = await this.messaging.rpc({
            model: 'llm.thread',
            method: 'read',
            args: [[threadId], ['name', 'model_id', 'provider_id', 'write_date']],
        });
        if (!threadDetails || !threadDetails[0]) {
            return;
        }

        // Insert the thread into frontend models
        await this.messaging.models['Thread'].insert({
            id: threadId,
            model: 'llm.thread',
            name: threadDetails[0].name,
            message_needaction_counter: 0,
            isServerPinned: true,
            llmModel: defaultModel,
            llmChat: llmChat,
            updatedAt: threadDetails[0].write_date,
        });
        llmChat.selectThread(threadId);
    }
}

Object.assign(LLMChatSidebar, {
    props: { record: Object },
    template: 'llm_thread.LLMChatSidebar',
});

registerMessagingComponent(LLMChatSidebar);
