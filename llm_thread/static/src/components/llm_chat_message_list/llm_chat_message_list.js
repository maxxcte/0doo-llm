/** @odoo-module **/

import { MessageList } from '@mail/components/message_list/message_list';
import { Transition } from '@web/core/transition';
import { registerMessagingComponent } from '@mail/utils/messaging_component';
import { markup } from '@odoo/owl';
import { useEffect, useRef } from '@odoo/owl';

export class LLMChatMessageList extends MessageList {
    setup() {
        super.setup();
        this.rootRef = useRef('root'); // Reference to .o_MessageList
        useEffect(() => {
            if (this.rootRef.el) {
                this.rootRef.el.style.maxHeight = '500px'; // Fixed height for testing
                this.rootRef.el.style.overflow = 'auto'; // Ensure scrollable
            }
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
        const scrollable = this.rootRef.el;
        console.log("scrollToEnd called - scrollable:", scrollable);
        if (scrollable) {
            const scrollHeight = scrollable.scrollHeight;
            const clientHeight = scrollable.clientHeight;
            const scrollTop = scrollHeight - clientHeight;
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