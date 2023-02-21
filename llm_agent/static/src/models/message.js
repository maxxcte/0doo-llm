/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { attr } from '@mail/model/model_field';
registerPatch({
    name: 'Message',
    modelMethods: {
        /**
         * @override
         */
        convertData(data) {
            const data2 = this._super(data);
            if ('is_tool_message' in data) {
                data2.is_tool_message = data.is_tool_message;
            }
            return data2;
        },
    },
    fields:{
        is_tool_message: attr({
            default: false,
        }),
    },
});