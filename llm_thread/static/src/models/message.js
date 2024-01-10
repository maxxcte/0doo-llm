/** @odoo-module **/

import { attr } from "@mail/model/model_field";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "Message",
  modelMethods: {
    /**
     * @override
     */
    convertData(data) {
      const data2 = this._super(data);
      if ("is_tool_message" in data) {
        data2.is_tool_message = data.is_tool_message;
      }
      if ("user_vote" in data) {
        data2.user_vote = data.user_vote;
      }
      return data2;
    },
  },
  fields: {
    is_tool_message: attr({
      default: false,
    }),
    user_vote: attr({
      default: 0,
    }),
  },
});
