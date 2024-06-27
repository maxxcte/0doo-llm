/** @odoo-module **/

import { LLMChatThreadHeader } from "@llm_thread/components/llm_chat_thread_header/llm_chat_thread_header";
import { patch } from "@web/core/utils/patch";

patch(LLMChatThreadHeader.prototype, "llm_assistant.llm_assistant_dropdown_patch", {
  /**
   * Get all available assistants
   */
  get llmAssistants() {
    // Make sure we have a valid llmChat reference
    if (!this.llmChat) {
      return [];
    }

    // Return the assistants array
    return this.llmChat.llmAssistants || [];
  },

  /**
   * Handle assistant selection
   * @param {Object} assistant - The selected assistant
   */
  onSelectAssistant(assistant) {
    this.llmChatThreadHeaderView.saveSelectedAssistant(assistant.id);
  },

  /**
   * Clear the selected assistant
   */
  onClearAssistant() {
    this.llmChatThreadHeaderView.saveSelectedAssistant(false);
  },
});
