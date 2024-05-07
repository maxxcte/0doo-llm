/** @odoo-module **/

import { attr } from "@mail/model/model_field";
import { registerPatch } from "@mail/model/model_core";

registerPatch({
  name: "Composer",
  fields: {
    placeholderLLMChat: attr({
      default: "Ask anything...",
    }),
    isSendDisabled: attr({
      compute() {
          return !this.canPostMessage;
      },
      default: true, // Assume disabled initially
    }),
    eventSource: attr({
      default: null,
    }),
  },
  recordMethods: {
    stopLLMThreadLoop() {
      // this should close event source
      this._closeEventSource();
    },
    async postUserMessageForLLM() {
      const thread = this.thread;
      
      const messageBody = this.textInputContent.trim();
      if (!messageBody || !thread) {
          return; // Or show warning
      }
  
      this.update({ textInputContent: '' });
  
      try {
          this.eventSource = new EventSource(
            `/llm/thread/generate?thread_id=${thread.id}&message=${messageBody}`,
          );
          this.eventSource.onmessage = async (event) =>{
            const data = JSON.parse(event.data);
            switch (data.type) {
              case 'end':
                this._closeEventSource();
                break;
            }
          }
          this.eventSource.onerror = (error) => {
            console.error("EventSource failed:", error);
            this._closeEventSource();
          };
      } catch (error) {
          console.error("Error sending LLM message:", error);
          this.messaging.notify({ message: this.env._t("Failed to send message."), type: 'danger' });
      } finally {
        for (const composerView of this.composerViews) {
          composerView.update({ doFocus: true });
        }
      }
    },
  },

  _closeEventSource(){
    if(this.eventSource){
      this.eventSource.close();
      this.update({ eventSource: null });
    }
  }
});
