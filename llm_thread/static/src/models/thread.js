/** @odoo-module **/

import { attr, one } from "@mail/model/model_field";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "Thread",
  fields: {
    llmChat: one("LLMChat", {
      inverse: "threads",
    }),
    activeLLMChat: one("LLMChat", {
      inverse: "activeThread",
    }),
    llmModel: one("LLMModel", {
      inverse: "threads",
    }),
    updatedAt: attr(),
    // Added for related thread functionality
    relatedThreadModel: attr(),
    // Added for related thread functionality
    relatedThreadId: attr(),
    relatedThread: one("Thread", {
      compute() {
        if (!this.relatedThreadModel || !this.relatedThreadId) {
          return;
        }
        return {
          model: this.relatedThreadModel,
          id: this.relatedThreadId,
        };
      },
    }),
  },
  recordMethods: {
    /**
     * Update thread settings
     * @param {Object} params
     * @param {String} [params.name] - New thread name
     * @param {Number} [params.llmModelId] - New model ID
     * @param {Number} [params.llmProviderId] - New provider ID
     */
    async updateLLMChatThreadSettings({
      name,
      llmModelId,
      llmProviderId,
    } = {}) {
      const values = {};

      // Only include name if it's a non-empty string
      if (typeof name === "string" && name.trim()) {
        values.name = name.trim();
      }

      // Only include model_id if it's a valid ID
      if (Number.isInteger(llmModelId) && llmModelId > 0) {
        values.model_id = llmModelId;
      } else if (this.llmModel?.id) {
        values.model_id = this.llmModel.id;
      }

      // Only include provider_id if it's a valid ID
      if (Number.isInteger(llmProviderId) && llmProviderId > 0) {
        values.provider_id = llmProviderId;
      } else if (this.llmModel?.llmProvider?.id) {
        values.provider_id = this.llmModel.llmProvider.id;
      }

      // Only make the RPC call if there are values to update
      if (Object.keys(values).length > 0) {
        await this.messaging.rpc({
          model: "llm.thread",
          method: "write",
          args: [[this.id], values],
        });
      }
    },
  },
});
