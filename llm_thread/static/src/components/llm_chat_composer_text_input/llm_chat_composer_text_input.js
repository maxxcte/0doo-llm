/** @odoo-module **/
import { ComposerTextInput } from "@mail/components/composer_text_input/composer_text_input";
import { registerMessagingComponent } from "@mail/utils/messaging_component";

export class LLMChatComposerTextInput extends ComposerTextInput {
  /**
   * Intercept input event before passing to composer view
   * @private
   * @param {InputEvent} ev
   */
  _onInput(ev) {
    // Call original handler
    this.composerView.onInputTextarea(ev);
  }

  /**
   * Intercept keydown event
   * @private
   * @param {KeyboardEvent} ev
   */
  _onKeydown(ev) {
    this.composerView.onKeydownTextareaForAi(ev);
  }
}

Object.assign(LLMChatComposerTextInput, {
  props: { record: Object },
  template: "llm_thread.LLMChatComposerTextInput",
});

registerMessagingComponent(LLMChatComposerTextInput);
