/** @odoo-module **/

import { attr } from "@mail/model/model_field";
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
  },
  recordMethods: {
    /**
     * Post AI message to the thread
     * @private
     * @param {String} body - The message body
     */
    async _postAIMessage(body) {
      const composer = this.composer;
      const params = {
        thread_id: composer.thread.id,
        body,
      };
      const messaging = this.messaging;
      const messageData = await messaging.rpc(
        { route: `/llm/thread/post_ai_response`, params },
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
    },

    /**
     * Stop streaming response for this thread
     */
    async _stopStreaming() {
      if (!this.isStreaming) {
        return;
      }
      this.update({ isStreaming: false, streamingContent: "" });
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
            {
              const htmlStreamingContent = this.htmlStreamingContent;
              eventSource.close();
              await this._postAIMessage(htmlStreamingContent);
              this._stopStreaming();
            }
            break;
        }
      };

      eventSource.onerror = (error) => {
        console.error("EventSource failed:", error);
        eventSource.close();
        this._stopStreaming();
      };
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
  },
});
