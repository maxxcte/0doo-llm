/** @odoo-module **/

import { registerPatch } from "@mail/model/model_core";
import { one } from "@mail/model/model_field";

registerPatch({
  name: "ThreadView",
  fields: {
    llmChatThreadHeaderView: one("LLMChatThreadHeaderView", {
      inverse: "threadView",
    }),
  },
});
