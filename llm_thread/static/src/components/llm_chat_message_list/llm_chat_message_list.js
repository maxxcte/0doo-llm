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
                // Calculate available height dynamically
                const parent = this.rootRef.el.closest('.o_LLMChatThread');
                if (parent) {
                    const parentHeight = parent.clientHeight;
                    const header = parent.querySelector('.o_LLMChatThread_header'); // Adjust selector if needed
                    const composer = parent.querySelector('.o_LLMChatThread_composer');
                    const headerHeight = header ? header.offsetHeight : 0;
                    const composerHeight = composer ? composer.offsetHeight : 0;
                    const availableHeight = parentHeight - headerHeight - composerHeight;
                    this.rootRef.el.style.maxHeight = `${availableHeight}px`;
                    this.rootRef.el.style.overflow = 'auto';
                    console.log("Set maxHeight:", availableHeight, "Parent:", parentHeight, "Header:", headerHeight, "Composer:", composerHeight);
                }
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