/** @odoo-module **/

import { attr, many } from "@mail/model/model_field";
import { clear } from "@mail/model/model_field_command";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "Thread",
  fields: {
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
     * Extended method to include tools in settings updates
     * @override
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
      }
    },
  },
});
