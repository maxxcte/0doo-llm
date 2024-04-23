/** @odoo-module **/

import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "ComposerView",
  recordMethods: {
    async _updateLLMThread(params){
      const thread = this.composer.thread;
      
      try {
        if (!thread || !thread.id) {
          throw new Error("Thread or Thread ID is missing.");
        }
        const result = await this.messaging.rpc({
            route: `/llm/thread/${thread.id}/update`, // Use the new route
            params: params,
        });
        if (result.status === 'error') {
            this.messaging.notify({ message: result.error, type: 'danger' });
        } else if (result.status === 'success') {
           console.log("updated LLM Thread successfully");
        }
      } catch (error) {
          console.error("Error updating LLMThread:", error);
          this.messaging.notify({ message: this.env._t("Failed to update LLM Thread."), type: 'danger' });
      } finally {
          this.update({ doFocus: true });
      }
    },
    async stopLLMThreadLoop() {
      // this should close event source
    },

    async postUserMessageForLLM() {
      const thread = this.composer.thread;
      
      const messageBody = this.composer.textInputContent.trim();
      if (!messageBody || !thread) {
          return; // Or show warning
      }
  
      this.composer.update({ textInputContent: '' });
  
      try {
          const eventSource = new EventSource(
            `/llm/thread/run?thread_id=${thread.id}&message=${messageBody}`,
          );
          eventSource.onmessage = async (event) =>{
            const data = JSON.parse(event.data);
            switch (data.type) {
              case 'end':
                eventSource.close();
                break;
            }
          }
          eventSource.onerror = (error) => {
            console.error("EventSource failed:", error);
            eventSource.close();
          };
      } catch (error) {
          console.error("Error sending LLM message:", error);
          this.messaging.notify({ message: this.env._t("Failed to send message."), type: 'danger' });
      } finally {
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
