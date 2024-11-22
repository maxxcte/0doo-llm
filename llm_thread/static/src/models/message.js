/** @odoo-module **/

import { attr } from "@mail/model/model_field";
import { registerPatch } from "@mail/model/model_core";

/**
 * Helper function to safely parse JSON strings.
 * Returns defaultValue if parsing fails or input is invalid.
 * @param {string} jsonString - JSON string to parse
 * @param {any} [defaultValue=undefined] - Default value on failure
 * @returns {any} Parsed JSON or defaultValue
 */
function safeJsonParse(jsonString, defaultValue = undefined) {
  if (!jsonString || typeof jsonString !== 'string') {
      return defaultValue;
  }
  try {
      return JSON.parse(jsonString);
  } catch (e) {
      // console.warn("Failed to parse JSON string:", jsonString, e); // Optional logging
      return defaultValue; // Return default on error
  }
}

registerPatch({
  name: "Message",
  modelMethods: {
    /**
     * @override
     */
    convertData(data) {
      const data2 = this._super(data);
      if ("user_vote" in data) {
        data2.user_vote = data.user_vote;
      }
      if ("subtype_xmlid" in data) {
        data2.messageSubtypeXmlid = data.subtype_xmlid;
      }
      if ("tool_call_definition" in data) {
        data2.toolCallDefinition = data.tool_call_definition;
      }
      if ("tool_call_result" in data) {
        data2.toolCallResult = data.tool_call_result;
      }
      if ("tool_calls" in data) {
        data2.toolCallCalls = data.tool_calls;
      }
      if("tool_call_id" in data && data.tool_call_id !== null) {
        data2.toolCallId = data.tool_call_id;
      }
      return data2;
    },
  },
  fields: {
    user_vote: attr({
      default: 0,
    }),
    /**
     * Compute parsed tool call definition from llm_tool_call_definition field.
     */
    toolCallDefinition: attr({}),
    toolCallDefinitionFormatted: attr({
      compute() {
        return safeJsonParse(this.toolCallDefinition);
    },
    }),
    toolCallResult: attr({
      default: "",
    }),
    toolCallId: attr({
      default: null,
    }),
    /**
     * Compute parsed tool call result data from llm_tool_call_result field.
     */
    toolCallResultData: attr({
        compute() {
            // Uses the field added by llm_thread's python patch
            return safeJsonParse(this.toolCallResult);
        },
    }),
    /**
     * Compute boolean indicating if the tool call result is an error.
     */
    toolCallResultIsError: attr({
        compute() {
            const resultData = this.toolCallResultData; // Uses the computed field above
            // Check if it's an object and has an 'error' key
            return typeof resultData === 'object' && resultData !== null && 'error' in resultData;
        },
    }),
    /**
     * Compute formatted tool call result string (e.g., pretty JSON).
     */
    toolCallResultFormatted: attr({
        compute() {
            const resultData = this.toolCallResultData; // Uses the computed field
            if (resultData === undefined || resultData === null) {
                return "";
            }
            try {
                // Only pretty print if it's likely an object/array
                return typeof resultData === 'object'
                    ? JSON.stringify(resultData, null, 2) // Pretty print with 2 spaces
                    : String(resultData); // Otherwise, just convert to string
            } catch (e) {
                console.error("Error formatting tool call result:", e);
                return String(resultData); // Fallback to simple string conversion
            }
        },
    }),
    toolCallCalls: attr({
      default: [],
    }),
    /**
     * Compute parsed list of tool calls requested by an assistant message.
     */
    formattedToolCalls: attr({
        compute() {
            // Uses the field added by llm_thread's python patch
            // parseJson returns undefined on failure, default to empty array for template
            return safeJsonParse(this.toolCallCalls, []); // Default to empty array
        },
    }),
    /**
     * Compute the subtype XML ID (useful for templates).
     * Requires message_format to add subtype_xmlid to the payload.
     */
    messageSubtypeXmlid: attr({}),
  },
});
