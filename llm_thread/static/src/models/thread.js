/** @odoo-module **/

import { attr, many, one } from "@mail/model/model_field";
import { clear } from "@mail/model/model_field_command";
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
    // Track selected tool IDs for this thread
    selectedToolIds: attr({
      default: [],
    }),

    // Computed field to get selected tools information
    selectedTools: many("LLMTool", {
      compute() {
        if (!this.selectedToolIds || !this.llmChat?.tools) {
          return clear();
        }

        return this.llmChat.tools.filter((tool) =>
          this.selectedToolIds.includes(tool.id)
        );
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
      toolIds,
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

      // Handle tools if provided
      if (Array.isArray(toolIds)) {
        values.tool_ids = [[6, 0, toolIds]];
      }

      // Only make the RPC call if there are values to update
      if (Object.keys(values).length > 0) {
        await this.messaging.rpc({
          model: "llm.thread",
          method: "write",
          args: [[this.id], values],
        });
        
        // If this thread is part of an LLMChat, use the refreshThread method to update it
        if (this.llmChat) {
          await this.llmChat.refreshThread(this.id);
        }
      }
    },
  },
});
