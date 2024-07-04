/** @odoo-module **/

import { attr, many } from "@mail/model/model_field";
import { registerModel } from "@mail/model/model_core";

/**
 * Model for LLM Assistant
 */
registerModel({
  name: "LLMAssistant",
  fields: {
    id: attr({
      identifying: true,
    }),
    name: attr(),
    /**
     * Threads associated with this assistant
     */
    threads: many("Thread", {
      inverse: "llmAssistant",
    }),
  },
});
