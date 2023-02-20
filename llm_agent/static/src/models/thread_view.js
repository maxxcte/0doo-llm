/** @odoo-module **/

import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "ThreadView",
  recordMethods: {
    /**
     * Override _shouldMessageBeSquashed to handle tool messages
     * 
     * @override
     * @param {Message} prevMessage
     * @param {Message} message
     * @returns {boolean}
     */
    _shouldMessageBeSquashed(prevMessage, message) {
      // First check if the messages have different subtypes
      // TODO check how to detect subtype_id in order to prevent squashing
      
      // Call the original implementation for other cases
      return this._super(...arguments);
    },
  },
});