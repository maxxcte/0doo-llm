/** @odoo-module **/

import { registerMessagingComponent } from "@mail/utils/messaging_component";
import { useComponentToModel } from "@mail/component_hooks/use_component_to_model";
const { Component } = owl;

export class LLMChatComposer extends Component {
  /**
   * @override
   */
  setup() {
    super.setup();
    useComponentToModel({ fieldName: "component" });
  }
  /**
   * @returns {ComposerView}
   */
  get composerView() {
    return this.props.record;
  }

  /**
   * @returns {Boolean}
   */
  get isDisabled() {
    // Read the computed disabled state from the model.
    return this.composerView.composer.isSendDisabled;
  }

  get isStreaming(){
    return this.composerView.composer.thread.state === 'streaming';
  }

  get isRequestedStop(){
    return this.composerView.composer.thread.state === 'requested_stop';
  }

  // --------------------------------------------------------------------------
  // Private
  // --------------------------------------------------------------------------

  /**
   * Intercept send button click
   * @private
   */
  _onClickSend() {
    if (this.isDisabled) {
      return;
    }

    this.composerView.postUserMessageForLLM();
  }
  /**
   * Handles click on the stop button.
   *
   * @private
   */
  _onClickStop() {
    this.composerView.stopLLMThreadLoop();
  }
}

Object.assign(LLMChatComposer, {
  props: { record: Object },
  template: "llm_thread.LLMChatComposer",
});

registerMessagingComponent(LLMChatComposer);
