/** @odoo-module **/

import { attr, many } from "@mail/model/model_field";
import { markdownToHtml } from "../utils/markdown_utils";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "ComposerView",
  fields: {
    // Streaming related fields
    isStreaming: attr({
      default: false,
    }),
    streamingContent: attr({
      default: "",
    }),
    // Computed field from streaming content
    htmlStreamingContent: attr({
      compute() {
        return markdownToHtml(this.streamingContent);
      },
    }),
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
    // Flag to track if the current streaming content is from a tool
    isToolContent: attr({
      default: false,
    }),
    // Flag to prevent multiple interpretation requests
    isInterpretationRequested: attr({
      default: false,
    }),
    pendingToolMessages: many("LLMToolMessage", {
      inverse: "composerView",
    }),
    isSendDisabled: attr({
      compute() {
        // Disabled if composer can't post (empty, uploading) OR if LLM is streaming
        return !this.composer?.canPostMessage || this.isStreaming;
      },
      // Assume disabled by default until computed
      default: true,
    }),
    // Store the active EventSource connection
    eventSource: attr(),
  },
  recordMethods: {
    /**
     * Post a message to the thread
     * @param {String} content - HTML content to post
     * @param {String} toolCallId - Optional tool call ID for tool messages
     * @private
     */
    async _postAIMessage(content, toolCallId = false) {
      const threadId = this.composer.thread.id;
      const data = {
        body: content,
        thread_id: threadId,
      };

      // If this is a tool message, add the tool_call_id and subtype
      if (toolCallId) {
        data.tool_call_id = toolCallId;
        data.subtype_xmlid = "llm_tool.mt_tool_message";

        // Find the tool message to get the function name
        const toolMessage = this.pendingToolMessages.find(
          (msg) => msg.toolCallId === toolCallId
        );
        if (toolMessage) {
          data.tool_name = toolMessage.functionName;
        }
      }

      const messaging = this.messaging;
      try {
        const messageData = await messaging.rpc(
          { route: `/llm/thread/post_ai_response`, params: data },
          { shadow: true }
        );

        if (!messaging.exists()) {
          return;
        }

        const message = messaging.models.Message.insert(
          messaging.models.Message.convertData(messageData)
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

        // Clear the pending tool message after it's posted
        if (toolCallId) {
          const messageToRemove = this.pendingToolMessages.find(
            (msg) => msg.toolCallId === toolCallId
          );
          if (messageToRemove) {
            messageToRemove.delete();
          }
        }

        return message;
      } catch (error) {
        console.error("Error posting message:", error);
      }
    },

    /**
     * Stop streaming response for this thread
     */
    _stopStreaming() {
      this._closeEventSource();

      // Delete all pending tool messages
      for (const toolMessage of this.pendingToolMessages) {
        toolMessage.delete();
      }

      this.update({
        isStreaming: false,
        streamingContent: "",
        isToolActive: false,
        currentToolCallId: false,
        currentToolName: "",
        toolArguments: "",
        toolResult: "",
        isToolContent: false,
        isInterpretationRequested: false,
      });
    },
    /**
     * Start streaming response for this thread
     */
    async startStreaming() {
      // Close any existing connection before starting a new one
      this._closeEventSource();

      const defaultContent = "Thinking...";
      if (this.isStreaming) {
        return;
      }
      const composer = this.composer;

      // Delete any existing pending tool messages
      for (const toolMessage of this.pendingToolMessages) {
        toolMessage.delete();
      }

      this.update({
        isStreaming: true,
        streamingContent: defaultContent,
        isToolContent: false,
      });

      // Store the EventSource instance on the model
      this.update({
        eventSource: new EventSource(
          `/llm/thread/stream_response?thread_id=${composer.thread.id}`
        ),
      });

      this.eventSource.onmessage = async (event) => {
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
              // Clear streaming content for tool
              streamingContent: "",
              // Mark that we're now dealing with tool content
              isToolContent: true,
            });
            break;
          case "tool_end":
            // Handle tool end event
            this.update({
              toolResult: data.content,
              isToolActive: false,
            });

            console.log("Tool ended");

            // Create a new LLMToolMessage record with tool_call_id as the identifier
            this.messaging.models.LLMToolMessage.insert({
              id: data.tool_call_id,
              content: markdownToHtml(data.formatted_content),
              toolCallId: data.tool_call_id,
              functionName: this.currentToolName,
              arguments: this.toolArguments,
              result: data.content,
              composerView: this,
            });
            break;
          case "error":
            console.error("Streaming error:", data.error);
            this.eventSource.close();
            this.update({ isStreaming: false, eventSource: undefined });
            this.messaging.notify({
              message: data.error,
              type: "danger",
            });
            break;
          case "end":
            this._closeEventSource();
            this._handleStreamingEnd();
            break;
        }
      };

      this.eventSource.onerror = (error) => {
        console.error("EventSource failed:", error);
        // Safely close if it exists
        this._closeEventSource();
        this._stopStreaming();
      };
    },

    /**
     * Handle the end of a streaming session
     * Post any content and tool messages, then start interpretation if needed
     * @private
     */
    async _handleStreamingEnd() {
      // Post any regular content if we have some and it's not tool-related content
      if (this.streamingContent && !this.isToolContent) {
        const htmlStreamingContent = this.htmlStreamingContent;
        await this._postAIMessage(htmlStreamingContent);
      }

      // Post all pending tool messages
      if (this.pendingToolMessages.length > 0) {
        console.log(
          `Posting ${this.pendingToolMessages.length} pending tool messages`
        );

        // Post all tool messages in sequence
        for (const toolMessage of this.pendingToolMessages) {
          await this._postAIMessage(
            toolMessage.content,
            toolMessage.toolCallId
          );
        }

        // Only start interpretation after all tool messages are posted
        // and if this is the initial streaming (not already interpreting)
        if (this.isToolContent && !this.isInterpretationRequested) {
          console.log("Starting interpretation streaming");

          // First, clean up the current streaming session
          // but preserve the isToolContent flag
          const wasToolContent = this.isToolContent;
          this._stopStreaming();

          // Then set up for interpretation
          this.update({
            isInterpretationRequested: true,
            isToolContent: wasToolContent,
          });

          // Small delay to ensure messages are fully processed
          setTimeout(() => this.startInterpretationStreaming(), 500);
          // Exit early, we'll handle the interpretation streaming separately
          return;
        }
      }

      // If we get here, either:
      // 1. This is the end of a regular streaming session with no tool calls
      // 2. This is the end of an interpretation streaming session
      console.log(
        "Ending streaming session, isInterpretation:",
        this.isInterpretationRequested
      );
      this._stopStreaming();
    },

    /**
     * Start streaming for interpretation after tool calls
     */
    startInterpretationStreaming() {
      // Set flag to prevent multiple interpretation requests
      this.update({ isInterpretationRequested: true });

      // Start a new streaming session for interpretation
      this.startStreaming();

      console.log("Started interpretation streaming");
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
      // UP, DOWN, TAB: prevent moving cursor if navigation in mention suggestions
      switch (ev.key) {
        case "Escape":
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
          // Prevent sending if the composer is disabled (e.g., empty, uploading, or LLM streaming)
          if (this.isSendDisabled) {
            // Prevent default Enter behavior (like newline)
            ev.preventDefault();
            // Stop processing
            return;
          }
          this.onKeydownTextareaEnterForAi(ev);
          break;
      }
    },
    /**
     * Check if the keyboard event matches a specific shortcut
     * @param {KeyboardEvent} ev - The keyboard event
     * @param {String} shortcutType - The type of shortcut to check
     * @returns {Boolean} - Whether the event matches the shortcut
     * @private
     */
    _matchesShortcut(ev, shortcutType) {
      if (shortcutType === "ctrl-enter") {
        return !ev.altKey && ev.ctrlKey && !ev.metaKey && !ev.shiftKey;
      } else if (shortcutType === "enter") {
        return !ev.altKey && !ev.ctrlKey && !ev.metaKey && !ev.shiftKey;
      } else if (shortcutType === "meta-enter") {
        return !ev.altKey && !ev.ctrlKey && ev.metaKey && !ev.shiftKey;
      }
      return false;
    },

    /**
     * Handle keyboard shortcuts for sending messages
     * @param {KeyboardEvent} ev - The keyboard event
     * @returns {Boolean} - Whether a shortcut was handled
     * @private
     */
    _handleSendShortcuts(ev) {
      for (const shortcut of this.sendShortcuts) {
        if (this._matchesShortcut(ev, shortcut)) {
          this.postUserMessageForAi();
          ev.preventDefault();
          return true;
        }
      }
      return false;
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

      this._handleSendShortcuts(ev);
    },

    /**
     * Safely closes the current EventSource connection and clears the reference.
     * @private
     */
    _closeEventSource() {
      if (this.eventSource) {
        this.eventSource.close();
        this.update({ eventSource: undefined });
        console.log("EventSource connection closed and reference cleared.");
      }
    },
  },
});
