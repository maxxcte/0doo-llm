/** @odoo-module **/

import { one } from "@mail/model/model_field";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "ThreadView",
  fields: {
    llmChatThreadHeaderView: one("LLMChatThreadHeaderView", {
      inverse: "threadView",
    }),
  },
});
