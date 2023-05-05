/** @odoo-module **/

import { attr, one } from "@mail/model/model_field";
import { clear } from "@mail/model/model_field_command";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "LLMChatThreadHeaderView",
  fields: {
    /**
     * Selected agent ID
     */
    selectedAgentId: attr(),

    /**
     * Selected agent record
     */
    selectedAgent: one("LLMAgent", {
      compute() {
        if (!this.selectedAgentId) {
          return clear();
        }
        return this.threadView.thread.llmChat.llmAgents.find(
          (a) => a.id === this.selectedAgentId
        );
      },
    }),
  },
  recordMethods: {
    /**
     * Initialize or reset state based on current thread
     * @override
     * @private
     */
    _initializeState() {
      this._super();
      this.update({
        selectedAgentId: this.threadView.thread.llmAgent?.id,
      });
    },

    /**
     * Save selected agent to the thread
     * @param {Number|false} agentId - ID of the selected agent or false to clear
     */
    async saveSelectedAgent(agentId) {
      if (agentId === this.selectedAgentId) {
        return;
      }

      this.update({
        selectedAgentId: agentId,
      });

      await this.threadView.thread.updateLLMChatThreadSettings({
        agentId: agentId,
      });
    },
  },
});
