/** @odoo-module **/

import { attr } from "@mail/model/model_field";
import { registerModel } from "@mail/model/model_core";

/**
 * Model for LLM Agent
 */
registerModel({
  name: "LLMAgent",
  fields: {
    id: attr(),
    name: attr(),
  },
});
