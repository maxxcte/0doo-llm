/** @odoo-module **/

import { MessageList } from '@mail/components/message_list/message_list';
import { Transition } from '@web/core/transition';
import { registerMessagingComponent } from '@mail/utils/messaging_component';
import { markup } from '@odoo/owl';
export class LLMChatMessageList extends MessageList {
    get htmlStreamingContent() {
        return markup(this.composerView.htmlStreamingContent);
    }

    get composerView() {
        return this.props.composerView;
    }
}

Object.assign(LLMChatMessageList, {
    components: { Transition },
    props: { record: Object, composerView: Object },
    template: 'llm_thread.LLMChatMessageList',
});

registerMessagingComponent(LLMChatMessageList);