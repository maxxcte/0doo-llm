/** @odoo-module **/

import { LLMChatThreadHeader } from "@llm_thread/components/llm_chat_thread_header/llm_chat_thread_header";
import { patch } from "@web/core/utils/patch";

patch(
  LLMChatThreadHeader.prototype,
  "llm_agent/static/src/components/llm_chat_thread_header/llm_chat_thread_header_patch.js",
  {
    /**
     * @override
     */
    setup() {
      this._super.apply(this, arguments);
      // Bind the method to ensure correct context
      this.onToolSelectChange = this.onToolSelectChange.bind(this);
    },
    /**
     * Handle tool selection change
     * @param {Event} ev - The checkbox change event
     * @param {Object} tool - The tool object being selected/deselected
     */
    async onToolSelectChange(ev, tool) {
      const checked = ev.target.checked;

      const newSelectedToolIds = checked
        ? [...this.thread.selectedToolIds, tool.id]
        : this.thread.selectedToolIds.filter((id) => id !== tool.id);

      // Update the thread settings with the new tool IDs

      await this.thread.updateLLMChatThreadSettings({
        toolIds: newSelectedToolIds,
      });
      this.thread.update({
        selectedToolIds: newSelectedToolIds,
      });
    },
  }
);
