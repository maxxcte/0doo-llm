/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { LLMChatThreadHeader } from "@llm_thread/components/llm_chat_thread_header/llm_chat_thread_header";

patch(LLMChatThreadHeader.prototype,"llm_agent.llm_agent_dropdown_patch", {
  /**
   * Get all available agents
   */
  get llmAgents() {
    return this.llmChat.llmAgents || [];
  },

  /**
   * Handle agent selection
   * @param {Object} agent - The selected agent
   */
  onSelectAgent(agent) {
    this.llmChatThreadHeaderView.saveSelectedAgent(agent.id);
  },

  /**
   * Clear the selected agent
   */
  onClearAgent() {
    this.llmChatThreadHeaderView.saveSelectedAgent(false);
  }
});
