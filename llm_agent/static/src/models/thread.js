/** @odoo-module **/

import { one } from "@mail/model/model_field";
import { registerPatch } from "@mail/model/model_core";

/**
 * Patch the Thread model to add llmAgent field
 */
registerPatch({
  name: "Thread",
  fields: {
    /**
     * The LLM agent associated with this thread
     */
    llmAgent: one("LLMAgent", {
      inverse: "threads",
    }),
  },
  recordMethods: {
    /**
     * Override updateLLMChatThreadSettings to handle agent
     * @override
     * @param {Object} settings - Settings object
     * @param {Number|false} [settings.agentId] - Agent ID to set, or false to clear
     */
    async updateLLMChatThreadSettings(settings = {}) {
      const { agentId, ...otherSettings } = settings;

      // Prepare additional values for the agent_id field
      const additionalValues = {};

      // Handle agent_id if provided
      if (agentId !== undefined) {
        additionalValues.agent_id = agentId || false;
      }

      // Call super with our additional values
      return this._super({
        ...otherSettings,
        additionalValues,
      });
    },
  },
});
