/** @odoo-module **/

import { registerModel } from "@mail/model/model_core";
import { attr, one, many } from "@mail/model/model_field";

registerModel({
  name: "LLMProvider",
  fields: {
    id: attr({
      identifying: true,
    }),
    name: attr({
      required: true,
    }),
    llmModels: many("LLMModel", {
      inverse: "llmProvider",
    }),
  },
});
