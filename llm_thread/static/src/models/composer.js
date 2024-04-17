/** @odoo-module **/

import { attr } from "@mail/model/model_field";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "Composer",
  fields: {
    placeholderLLMChat: attr({
      default: "Ask anything...",
    }),
    isSendDisabled: attr({
      compute() {
          return !this.canPostMessage;
      },
      default: true, // Assume disabled initially
    }),
  },
});
