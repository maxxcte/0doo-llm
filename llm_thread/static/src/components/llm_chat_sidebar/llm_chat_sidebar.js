/** @odoo-module **/

import { useModels } from '@mail/component_hooks/use_models';
import { registerMessagingComponent } from '@mail/utils/messaging_component';
import { Transition } from '@web/core/transition';
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
}

Object.assign(LLMChatSidebar, {
    props: { record: Object },
    components: { Transition },
    template: 'llm_thread.LLMChatSidebar',
});

registerMessagingComponent(LLMChatSidebar);
