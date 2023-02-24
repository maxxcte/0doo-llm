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
      if (prevMessage !== undefined && message !== undefined) {
        if (
          prevMessage.subtype_id !== undefined &&
          message.subtype_id !== undefined
        ) {
          if (
            prevMessage.subtype_id.length === 2 &&
            message.subtype_id.length === 2
          ) {
            if (prevMessage.subtype_id[0] !== message.subtype_id[0]) {
              return false;
            }
          }
        }
      }

      // Call the original implementation for other cases
      return this._super(...arguments);
    },
  },
});
