/** @odoo-module **/

import { useModels } from "@mail/component_hooks/use_models";
import { getMessagingComponent } from "@mail/utils/messaging_component";

const { Component, onWillDestroy } = owl;

export class LLMChatContainer extends Component {
  setup() {
    useModels();
    super.setup();
    onWillDestroy(() => this._willDestroy());

    this.env.services.messaging.modelManager.messagingCreatedPromise.then(
      async () => {
        const { action } = this.props;
        const initActiveId =
          (action.context && action.context.active_id) ||
          (action.params && action.params.default_active_id) ||
          null;

        if (!this.messaging.llmChat) {
          this.messaging.update({
            llmChat: {
              isInitThreadHandled: false,
            },
          });
        }
        this.llmChat = this.messaging.llmChat;
        this.llmChat.initializeLLMChat(action, initActiveId);
      }
    );

    // Keep track of current instance to handle cleanup
    LLMChatContainer.currentInstance = this;
  }

  get messaging() {
    return this.env.services.messaging.modelManager.messaging;
  }

  _willDestroy() {
    if (this.llmChat && LLMChatContainer.currentInstance === this) {
      this.llmChat.close();
    }
  }
}

Object.assign(LLMChatContainer, {
  props: {
    action: Object,
    actionId: { type: Number, optional: 1 },
    className: String,
    globalState: { type: Object, optional: 1 },
  },
  components: {
    LLMChat: getMessagingComponent("LLMChat"),
  },
  template: "llm_thread.LLMChatContainer",
});
