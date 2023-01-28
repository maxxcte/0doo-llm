/** @odoo-module **/

import { registerModel } from "@mail/model/model_core";
import { attr } from "@mail/model/model_field";

registerModel({
    name: "LLMTool",
    fields: {
        id: attr({
            identifying: true,
        }),
        name: attr({
            required: true,
        }),
    },
});