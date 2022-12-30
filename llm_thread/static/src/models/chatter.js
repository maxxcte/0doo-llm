/** @odoo-module **/

import { registerPatch } from "@mail/model/model_core";
import { attr, one } from "@mail/model/model_field";
import { clear } from "@mail/model/model_field_command";

registerPatch({
  name: "Chatter",
  fields: {
    is_chatting_with_ai: attr({ default: false }),
    llmChatThread: one("Thread", {
      compute() {
        if (!this.is_chatting_with_ai || !this.llmChatThreadView) {
          return clear();
        }
        return this.llmChatThreadView.thread;
      },
    }),
    llmChatThreadView: one("ThreadView", {
      compute() {
        if (!this.is_chatting_with_ai || !this.thread) {
          return clear();
        }
        const llmChat = this.messaging.llmChat;
        if (!llmChat || !llmChat.activeThread || !llmChat.llmChatView) {
          return clear();
        }
        return {
          threadViewer: llmChat.llmChatView.threadViewer,
          messageListView: {},
          llmChatThreadHeaderView: {},
        };
      },
    }),
  },
  recordMethods: {
    /**
     * Toggles AI chat mode, initializing LLMChat and selecting/creating a thread.
     */
    async toggleAIChat() {
      if (!this.thread) return;

      const messaging = this.messaging;
      if (!this.is_chatting_with_ai) {
        let llmChat = messaging.llmChat;
        if (!llmChat) {
          messaging.update({ llmChat: { isInitThreadHandled: false } });
          llmChat = messaging.llmChat;
        }
        if(!llmChat.llmChatView) {
            llmChat.open();
        }

        try {
          const thread = await llmChat.ensureThread({
            relatedThreadModel: this.thread.model,
            relatedThreadId: this.thread.id,
          });
          if (!thread) {
            throw new Error("Failed to ensure thread");
          }

          await llmChat.selectThread(thread.id);
          this.update({ is_chatting_with_ai: true });
        } catch (error) {
          messaging.notify({
            title: "Failed to Start AI Chat",
            message: error.message || "An error occurred",
            type: "danger",
          });
        }
      } else {
        this.update({ is_chatting_with_ai: false });
      }
    },
  },
});
