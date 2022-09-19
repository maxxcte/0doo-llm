/** @odoo-module **/

import { MessageList } from '@mail/components/message_list/message_list';
import { Transition } from '@web/core/transition';
import { registerMessagingComponent } from '@mail/utils/messaging_component';

export class LLMChatMessageList extends MessageList {
}

Object.assign(LLMChatMessageList, {
    components: { Transition },
    props: { record: Object },
    template: 'llm_thread.LLMChatMessageList',
});

registerMessagingComponent(LLMChatMessageList);