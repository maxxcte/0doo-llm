/** @odoo-module **/

import { many } from "@mail/model/model_field";
import { registerPatch } from "@mail/model/model_core";

// Define agent-related fields to fetch from server
const AGENT_THREAD_FIELDS = ["agent_id"];

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
    },
    
    /**
     * Override loadThreads to include agent_id field
     * @override
     */
    async loadThreads(additionalFields = []) {
      // Call the super method with our additional fields
      return this._super([...additionalFields, ...AGENT_THREAD_FIELDS]);
    },
    
    /**
     * Override refreshThread to include agent_id field
     * @override
     */
    async refreshThread(threadId, additionalFields = []) {
      // Call the super method with our additional fields
      return this._super(threadId, [...additionalFields, ...AGENT_THREAD_FIELDS]);
    },
    
    /**
     * Override _mapThreadDataFromServer to add agent information
     * @override
     */
    _mapThreadDataFromServer(threadData) {
      // Get the base mapped data from super
      const mappedData = this._super(threadData);
      
      // Add agent information if present
      if (threadData.agent_id) {
        mappedData.llmAgent = {
          id: threadData.agent_id[0],
          name: threadData.agent_id[1],
        };
      }
      
      return mappedData;
    }
  },
});
