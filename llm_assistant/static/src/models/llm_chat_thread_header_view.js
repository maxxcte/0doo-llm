/** @odoo-module **/

import { attr, one } from "@mail/model/model_field";
import { clear } from "@mail/model/model_field_command";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "LLMChatThreadHeaderView",
  fields: {
    /**
     * Selected assistant ID
     */
    selectedAssistantId: attr(),

    /**
     * Selected assistant record
     */
    selectedAssistant: one("LLMAssistant", {
      compute() {
        if (!this.selectedAssistantId) {
          return clear();
        }
        // This now searches within a collection of LLMAssistant records
        // and returns a record instance, which is correct.
        return this.threadView.thread.llmChat.llmAssistants.find(
          (assistantRecord) => assistantRecord.id === this.selectedAssistantId
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
        selectedAssistantId: this.threadView.thread.llmAssistant?.id || false,
      });
    },

    /**
     * Save selected assistant to the thread using the dedicated endpoint
     * @param {Number|false} assistantId - ID of the selected assistant or false to clear
     */
    async saveSelectedAssistant(assistantId) {
      if (assistantId === this.selectedAssistantId) {
        return;
      }

      // Update the local state immediately for responsive UI
      this.update({
        selectedAssistantId: assistantId || false,
      });

      // Call the dedicated endpoint to set the assistant
      const result = await this.messaging.rpc({
        route: "/llm/thread/set_assistant",
        params: {
          thread_id: this.threadView.thread.id,
          assistant_id: assistantId,
        },
      });

      if (result.success) {
        // Refresh the thread to get updated data
        await this.threadView.thread.llmChat.refreshThread(
          this.threadView.thread.id
        );
        if (assistantId === false) {
          this.update({
            selectedAssistantId: false,
          });
        } else {
          this.update({
            selectedModelId: this.threadView.thread.llmModel?.id,
            selectedProviderId:
              this.threadView.thread.llmModel?.llmProvider?.id,
          });
        }
      } else {
        // Revert the local state if the server call failed
        this.update({
          selectedAssistantId: this.threadView.thread.llmAssistant?.id || false,
        });

        // Show error message
        this.messaging.notify({
          type: "warning",
          message: "Failed to update assistant",
        });
      }
    },
  },
});
