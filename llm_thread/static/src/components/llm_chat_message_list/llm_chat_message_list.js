/** @odoo-module **/

import { MessageList } from '@mail/components/message_list/message_list';
import { Transition } from '@web/core/transition';
import { registerMessagingComponent } from '@mail/utils/messaging_component';
import { markup } from '@odoo/owl';
import { useEffect } from '@odoo/owl';

export class LLMChatMessageList extends MessageList {
    setup() {
        super.setup();
        useEffect(() => {
            if (this.composerView.isStreaming && this.htmlStreamingContent) {
                console.log("Triggered useEffect - isStreaming:", this.composerView.isStreaming, "htmlStreamingContent:", this.htmlStreamingContent);
                this._scrollToEnd();
            }
        }, () => [this.htmlStreamingContent]);
    }

    get htmlStreamingContent() {
        return this.composerView.htmlStreamingContent ? markup(this.composerView.htmlStreamingContent) : '';
    }

    get composerView() {
        return this.props.composerView;
    }

    _scrollToEnd() {
        const { messageListView, order } = this._lastRenderedValues();
        const scrollable = messageListView.getScrollableElement();
        console.log("scrollToEnd called - scrollable:", scrollable, "order:", order);
        if (scrollable) {
            const scrollHeight = scrollable.scrollHeight;
            const clientHeight = scrollable.clientHeight;
            const scrollTop = order === 'asc' ? scrollHeight - clientHeight : 0;
            console.log("Scroll details - scrollHeight:", scrollHeight, "clientHeight:", clientHeight, "scrollTop:", scrollTop);
            scrollable.scrollTop = scrollTop;
            console.log("After scroll - current scrollTop:", scrollable.scrollTop);
        } else {
            console.log("No scrollable element found!");
        }
    }
}

Object.assign(LLMChatMessageList, {
    components: { Transition },
    props: { record: Object, composerView: Object },
    template: 'llm_thread.LLMChatMessageList',
});

registerMessagingComponent(LLMChatMessageList);