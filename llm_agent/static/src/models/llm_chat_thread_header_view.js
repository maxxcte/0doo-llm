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
     * Save selected agent to the thread using the dedicated endpoint
     * @param {Number|false} agentId - ID of the selected agent or false to clear
     */
    async saveSelectedAgent(agentId) {
      if (agentId === this.selectedAgentId) {
        return;
      }

      // Update the local state immediately for responsive UI
      this.update({
        selectedAgentId: agentId,
      });

      // Call the dedicated endpoint to set the agent
      const result = await this.messaging.rpc({
        route: '/llm/thread/set_agent',
        params: {
          thread_id: this.threadView.thread.id,
          agent_id: agentId,
        },
      });
      
      if (result.success) {
        // Refresh the thread to get updated data
        await this.threadView.thread.llmChat.refreshThread(this.threadView.thread.id);
        if(agentId !== false){
          this.update({
            selectedModelId: this.threadView.thread.llmModel?.id,
            selectedProviderId: this.threadView.thread.llmModel?.llmProvider?.id,
          });
        }
      } else {
        // Revert the local state if the server call failed
        this.update({
          selectedAgentId: this.threadView.thread.llmAgent?.id,
        });
        
        // Show error message
        this.messaging.notify({
          type: 'warning',
          message: 'Failed to update agent',
        });
      }
    },
  },
});
