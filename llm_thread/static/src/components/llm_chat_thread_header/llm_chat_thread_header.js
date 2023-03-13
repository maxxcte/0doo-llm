/** @odoo-module **/
import { registerMessagingComponent } from "@mail/utils/messaging_component";
import { useRefToModel } from "@mail/component_hooks/use_ref_to_model";

const { Component } = owl;

export class LLMChatThreadHeader extends Component {
  /**
   * @override
   */
  setup() {
    super.setup();
    useRefToModel({
      fieldName: "llmChatThreadNameInputRef",
      refName: "threadNameInput",
    });
  }

  get llmChatThreadHeaderView() {
    return this.props.record;
  }

  get threadView() {
    return this.llmChatThreadHeaderView.threadView;
  }

  get thread() {
    return this.threadView.thread;
  }

  get llmChat() {
    return this.thread.llmChat;
  }

  get llmProviders() {
    return this.llmChat.llmProviders;
  }

  get llmModels() {
    return this.llmChat.llmModels;
  }

  get isSmall() {
    return this.messaging.device.isSmall;
  }

  /**
   * @param {Object} provider
   */
  onSelectProvider(provider) {
    if (provider.id !== this.llmChatThreadHeaderView.selectedProviderId) {
      const defaultModel = this.getDefaultModelForProvider(provider.id);
      // It should trigger onChange event
      this.llmChatThreadHeaderView.saveSelectedModel(defaultModel?.id);
      this.messaging.notify({
        title: "Model have been reset",
        message: "We have auto updated model to default one for this provider",
        type: "info",
      });
    }
  }

  getDefaultModelForProvider(providerId) {
    const availableModels =
      this.llmModels?.filter((model) => model.llmProvider?.id === providerId) ||
      [];
    const defaultModel = availableModels.find((model) => model.default);

    if (defaultModel) {
      return defaultModel;
    } else if (availableModels.length > 0) {
      return availableModels[0];
    }
    return null;
  }

  /**
   * @param {Object} model
   */
  onSelectModel(model) {
    this.llmChatThreadHeaderView.saveSelectedModel(model.id);
  }

  /**
   * Toggle thread list visibility on mobile
   */
  _onToggleThreadList() {
    this.thread.llmChat.llmChatView.update({
      isThreadListVisible: !this.thread.llmChat.llmChatView.isThreadListVisible,
    });
  }

  /**
   * Handle keydown in thread name input
   * @param {KeyboardEvent} ev
   */
  onKeyDownThreadNameInput(ev) {
    switch (ev.key) {
      case "Enter":
        ev.preventDefault();
        this.llmChatThreadHeaderView.saveThreadName();
        break;
      case "Escape":
        ev.preventDefault();
        this.llmChatThreadHeaderView.discardThreadNameEdition();
        break;
    }
  }

  /**
   * Handle input value change
   * @param {Event} ev
   */
  onInputThreadNameInput(ev) {
    this.llmChatThreadHeaderView.update({ pendingName: ev.target.value });
  }
}

Object.assign(LLMChatThreadHeader, {
  props: { record: Object },
  template: "llm_thread.LLMChatThreadHeader",
});

registerMessagingComponent(LLMChatThreadHeader);
