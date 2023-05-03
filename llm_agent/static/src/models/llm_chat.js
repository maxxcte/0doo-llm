/** @odoo-module **/

import { many } from "@mail/model/model_field";
import { registerPatch } from "@mail/model/model_core";

/**
 * Patch the LLMChat model to add agents
 */
registerPatch({
  name: "LLMChat",
  fields: {
    llmAgents: many("LLMAgent"),
  },
  recordMethods: {
    /**
     * Load agents from the server
     */
    async loadAgents() {
      const result = await this.messaging.rpc({
        model: "llm.agent",
        method: "search_read",
        kwargs: {
          domain: [],
          fields: ["name"],
        },
      });

      const agentData = result.map(agent => ({
        id: agent.id,
        name: agent.name,
      }));

      this.update({ llmAgents: agentData });
    },
    
    /**
     * Override ensureThread to load agents as well
     * @override
     */
    async ensureThread(options) {
      // Load agents if not already loaded
      if (!this.llmAgents || this.llmAgents.length === 0) {
        await this.loadAgents();
      }
      
      // Call the original method
      return this._super(options);
    },
    
    /**
     * Override initializeLLMChat to include agent loading
     * @override
     */
    async initializeLLMChat(action, initActiveId, postInitializationPromises = []) {
      // Pass our loadAgents promise to the original method
      return this._super(action, initActiveId, [...postInitializationPromises, this.loadAgents()]);
    }
  },
});
