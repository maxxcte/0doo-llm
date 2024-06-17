/** @odoo-module **/

import { attr, many } from "@mail/model/model_field";
import { registerModel } from "@mail/model/model_core";

/**
 * Model for LLM Agent
 */
registerModel({
  name: "LLMAgent",
  fields: {
    id: attr({
      identifying: true,
    }),
    name: attr(),
    /**
     * Threads associated with this agent
     */
    threads: many("Thread", {
      inverse: "llmAgent",
    }),
  },
});
