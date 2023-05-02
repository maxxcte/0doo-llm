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
  },
});
