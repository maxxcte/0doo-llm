/** @odoo-module **/

import { one } from "@mail/model/model_field";
import { registerPatch } from "@mail/model/model_core";

/**
 * Patch the Thread model to add llmAssistant field
 */
registerPatch({
  name: "Thread",
  fields: {
    /**
     * The LLM assistant associated with this thread
     */
    llmAssistant: one("LLMAssistant", {
      inverse: "threads",
    }),
  },
  recordMethods: {
    /**
     * Override updateLLMChatThreadSettings to handle assistant
     * @override
     * @param {Object} settings - Settings object
     * @param {Number|false} [settings.assistantId] - Assistant ID to set, or false to clear
     */
    async updateLLMChatThreadSettings(settings = {}) {
      const { assistantId, ...otherSettings } = settings;

      // Prepare additional values for the assistant_id field
      const additionalValues = {};

      // Handle assistant_id if provided
      if (assistantId !== undefined) {
        additionalValues.assistant_id = assistantId || false;
      }

      // Call super with our additional values
      return this._super({
        ...otherSettings,
        additionalValues,
      });
    },
  },
});
