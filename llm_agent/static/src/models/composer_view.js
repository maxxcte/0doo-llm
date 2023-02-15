/** @odoo-module **/

import { registerPatch } from "@mail/model/model_core";
import { attr } from "@mail/model/model_field";
import { markdownToHtml } from "@mail/utils/common/format";

registerPatch({
  name: "ComposerView",
  fields: {
    // Tool handling related fields
    isToolActive: attr({
      default: false,
    }),
    currentToolCallId: attr({
      default: false,
    }),
    currentToolName: attr({
      default: "",
    }),
    toolArguments: attr({
      default: "",
    }),
    toolResult: attr({
      default: "",
    }),
    // Streaming related fields
    isStreaming: attr({
      default: false,
    }),
    streamingContent: attr({
      default: "",
    }),
    // computed field from streaming content
    htmlStreamingContent: attr({
      compute() {
        return markdownToHtml(this.streamingContent);
      },
    }),
  },
  recordMethods: {
    /**
     * Post AI message to the thread
     * @private
     */
    async _postAIMessage(body, toolCallId = false) {
      const composer = this.composer;
      const params = {
        thread_id: composer.thread.id,
        body,
      };
      
      // If this is a tool message, add the tool_call_id and subtype
      if (toolCallId) {
        params.tool_call_id = toolCallId;
        params.subtype_xmlid = "llm_agent.mt_tool_message";
      }
      
      const messaging = this.messaging;
      let messageData = await messaging.rpc(
        { route: `/llm/thread/post_ai_response`, params },
        { shadow: true }
      );
      if (!messaging.exists()) {
        return;
      }
      const message = messaging.models["Message"].insert(
        messaging.models["Message"].convertData(messageData)
      );
      if (messaging.hasLinkPreviewFeature && !message.isBodyEmpty) {
        messaging.rpc(
          {
            route: `/mail/link_preview`,
            params: {
              message_id: message.id,
            },
          },
          { shadow: true }
        );
      }
      for (const threadView of message.originThread.threadViews) {
        // Reset auto scroll to be able to see the newly posted message.
        threadView.update({ hasAutoScrollOnMessageReceived: true });
        threadView.addComponentHint("message-posted", { message });
      }
    },

    /**
     * Stop streaming response for this thread
     */
    async _stopStreaming() {
      if (!this.isStreaming) {
        return;
      }
      this.update({ 
        isStreaming: false, 
        streamingContent: "",
        isToolActive: false,
        currentToolCallId: false,
        currentToolName: "",
        toolArguments: "",
        toolResult: ""
      });
    },
    
    /**
     * Start streaming response for this thread
     */
    async startStreaming() {
      const defaultContent = "Thinking...";
      if (this.isStreaming) {
        return;
      }
      const composer = this.composer;

      this.update({ isStreaming: true, streamingContent: defaultContent });
      const eventSource = new EventSource(
        `/llm/thread/stream_response?thread_id=${composer.thread.id}`
      );

      eventSource.onmessage = async (event) => {
        const data = JSON.parse(event.data);
        switch (data.type) {
          case "start":
            break;
          case "content":
            if (this.streamingContent === defaultContent) {
              this.update({ streamingContent: "" });
            }
            this.update({
              streamingContent: this.streamingContent + (data.content || ""),
            });
            break;
          case "tool_start":
            // Handle tool start event
            this.update({
              isToolActive: true,
              currentToolCallId: data.tool_call_id,
              currentToolName: data.function_name,
              toolArguments: data.arguments,
              streamingContent: "" // Clear streaming content for tool
            });
            break;
          case "tool_end":
            // Handle tool end event
            this.update({
              toolResult: data.content,
              isToolActive: false
            });
            
            // Post the tool message
            await this._postAIMessage(data.formatted_content, data.tool_call_id);
            
            // Start a new streaming session for interpretation if needed
            // This is optional based on your requirements
            // this.startInterpretationStreaming();
            break;
          case "error":
            console.error("Streaming error:", data.error);
            eventSource.close();
            this.update({ isStreaming: false });
            this.messaging.notify({
              message: data.error,
              type: "danger",
            });
            break;
          case "end":
            // Only post content if we have some and we're not in the middle of a tool call
            if (this.streamingContent && !this.isToolActive) {
              const htmlStreamingContent = this.htmlStreamingContent;
              await this._postAIMessage(htmlStreamingContent);
            }
            eventSource.close();
            this._stopStreaming();
            break;
        }
      };

      eventSource.onerror = (error) => {
        console.error("EventSource failed:", error);
        eventSource.close();
        this._stopStreaming();
      };
    },
    
    /**
     * Start streaming for interpretation after tool calls
     */
    async startInterpretationStreaming() {
      // This method would be implemented if you want to get interpretation
      // after tool calls are complete
      const composer = this.composer;
      
      // You would need a new endpoint for this or modify the existing one
      const eventSource = new EventSource(
        `/llm/thread/stream_interpretation?thread_id=${composer.thread.id}`
      );
      
      // Similar event handling as startStreaming
      // ...
    },
    
    async postUserMessageForAi() {
      await this.postMessage();
      this.update({
        doFocus: true,
      });
      this.startStreaming();
    },

    onKeydownTextareaForAi(ev) {
      if (!this.exists()) {
        return;
      }
      switch (ev.key) {
        case "Escape":
        // UP, DOWN, TAB: prevent moving cursor if navigation in mention suggestions
        case "ArrowUp":
        case "PageUp":
        case "ArrowDown":
        case "PageDown":
        case "Home":
        case "End":
        case "Tab":
          if (this.hasSuggestions) {
            // We use preventDefault here to avoid keys native actions but actions are handled in keyUp
            ev.preventDefault();
          }
          break;
        // ENTER: submit the message only if the dropdown mention proposition is not displayed
        case "Enter":
          this.onKeydownTextareaEnterForAi(ev);
          break;
      }
    },
    /**
     * @param {KeyboardEvent} ev
     */
    onKeydownTextareaEnterForAi(ev) {
      if (!this.exists()) {
        return;
      }
      if (this.hasSuggestions) {
        ev.preventDefault();
        return;
      }
      if (
        this.sendShortcuts.includes("ctrl-enter") &&
        !ev.altKey &&
        ev.ctrlKey &&
        !ev.metaKey &&
        !ev.shiftKey
      ) {
        this.postUserMessageForAi();
        ev.preventDefault();
        return;
      }
      if (
        this.sendShortcuts.includes("enter") &&
        !ev.altKey &&
        !ev.ctrlKey &&
        !ev.metaKey &&
        !ev.shiftKey
      ) {
        this.postUserMessageForAi();
        ev.preventDefault();
        return;
      }
      if (
        this.sendShortcuts.includes("meta-enter") &&
        !ev.altKey &&
        !ev.ctrlKey &&
        ev.metaKey &&
        !ev.shiftKey
      ) {
        this.postUserMessageForAi();
        ev.preventDefault();
        return;
      }
    },
  },
});
