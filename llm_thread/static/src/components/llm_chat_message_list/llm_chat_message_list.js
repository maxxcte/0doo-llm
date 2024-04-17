/** @odoo-module **/

import { markup, useEffect, useRef } from "@odoo/owl";

import { MessageList } from "@mail/components/message_list/message_list";
import { registerMessagingComponent } from "@mail/utils/messaging_component";
import { Transition } from "@web/core/transition";

export class LLMChatMessageList extends MessageList {
  setup() {
    super.setup();
    this.rootRef = useRef("root");
    // TODO Need to do it via addComponentHint probably
    useEffect(
      () => {
        if (this.thread && this.thread.state === 'streaming') {
          this._scrollToEnd();
        }
      },
      () => [this.thread.state]
    );
  }

  get thread() {
    return this.composerView.composer.thread;
  }

  get composerView() {
    return this.props.composerView;
  }

  _scrollToEnd() {
    const scrollable = this.rootRef.el.closest(".o_LLMChatThread_content");
    if (scrollable) {
      const scrollHeight = scrollable.scrollHeight;
      const clientHeight = scrollable.clientHeight;
      const scrollTop = scrollHeight - clientHeight;
      scrollable.scrollTop = scrollTop;
    } else {
      // Fallback to original behavior
      const fallbackScrollable = this.rootRef.el;
      if (fallbackScrollable) {
        const scrollHeight = fallbackScrollable.scrollHeight;
        const clientHeight = fallbackScrollable.clientHeight;
        const scrollTop = scrollHeight - clientHeight;
        fallbackScrollable.scrollTop = scrollTop;
      }
    }
  }
}

Object.assign(LLMChatMessageList, {
  components: { Transition },
  props: { record: Object, composerView: Object },
  template: "llm_thread.LLMChatMessageList",
});

registerMessagingComponent(LLMChatMessageList);
