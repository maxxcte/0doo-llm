/** @odoo-module **/
import { attr, one } from "@mail/model/model_field";
import { registerModel } from "@mail/model/model_core";

registerModel({
  name: "LLMToolMessage",
  fields: {
    id: attr({
      identifying: true,
    }),
    content: attr(),
    toolCallId: attr(),
    functionName: attr(),
    arguments: attr(),
    result: attr(),
    composerView: one("ComposerView", {
      inverse: "pendingToolMessages",
    }),
  },
});
