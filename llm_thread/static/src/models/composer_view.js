/** @odoo-module **/

import { attr, many } from "@mail/model/model_field";
import { markdownToHtml } from "../utils/markdown_utils";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "ComposerView",
  recordMethods: {
    async postUserMessageForLLM() {
      const thread = this.composer.thread;
      if(thread.state === 'streaming') {
        return;
      }
      const messageBody = this.composer.textInputContent.trim();
      if (!messageBody || !thread) {
          return; // Or show warning
      }
  
      // Optional: Immediately update UI state (e.g., clear input, maybe show temp message)
      this.composer.update({ textInputContent: '' });
      // Could potentially update thread state locally to 'streaming' optimistically
      // thread.update({ state: 'streaming' }); // Requires thread model patch
  
      try {
          const result = await this.messaging.rpc({
              route: `/llm/thread/${thread.id}/run`, // Use the new route
              params: {
                  message: messageBody, // Send as 'message' key
              },
          });
          // Controller returns simple status, actual updates via bus
          if (result.status === 'error') {
              this.messaging.notify({ message: result.error, type: 'danger' });
               // Reset thread state if needed (though backend finally block should handle it)
               // thread.update({ state: 'idle' });
          } else if (result.status === 'completed') {
             // Loop finished successfully on backend.
             // State should be updated via bus eventually, but can ensure idle here
             // thread.update({ state: 'idle' });
             console.log("LLM completion loop finished.");
          }
      } catch (error) {
          console.error("Error sending LLM message:", error);
          this.messaging.notify({ message: this.env._t("Failed to send message."), type: 'danger' });
           // Reset thread state on RPC error
           // thread.update({ state: 'idle' });
      } finally {
           // Ensure composer is focused or UI reset as needed
           this.update({ doFocus: true });
      }
    },

    onKeydownTextareaForLLM(ev) {
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
          if (this.composer.isSendDisabled || this.composer.thread.state === 'streaming') {
            // Prevent default Enter behavior (like newline)
            ev.preventDefault();
            // Stop processing
            return;
          }
          this.onKeydownTextareaEnterForLLM(ev);
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
          this.postUserMessageForLLM();
          ev.preventDefault();
          return true;
        }
      }
      return false;
    },

    /**
     * @param {KeyboardEvent} ev
     */
    onKeydownTextareaEnterForLLM(ev) {
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
