/** @odoo-module **/

import { registerPatch } from "@mail/model/model_core";
import { attr, one } from "@mail/model/model_field";
import { clear } from "@mail/model/model_field_command";

registerPatch({
    name: "Chatter",
    fields: {
        is_chatting_with_ai: attr({
            default: false,
        }),
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
        async toggleAIChat() {
            const messaging = this.messaging;
            if (!this.thread) {                
                return;
            }

            if (!this.is_chatting_with_ai) {
                let llmChat = messaging.llmChat;
                if (!llmChat) {
                    messaging.update({
                        llmChat: {
                            isInitThreadHandled: false,
                        },
                    });
                    llmChat = messaging.llmChat;
                }

                // Ensure llmChatView is initialized
                if (!llmChat.llmChatView) {
                    llmChat.open(); // This sets llmChatView: {}
                }

                if (llmChat.llmModels.length === 0) {
                    await llmChat.loadLLMModels();
                }
                if (llmChat.threads.length === 0) {
                    await llmChat.loadThreads();
                }

                let llmThread = llmChat.threads.find(
                    thread => thread.relatedThreadModel === this.thread.model &&
                            thread.relatedThreadId === this.thread.id
                );

                if (!llmThread) {
                    const defaultModel = llmChat.defaultLLMModel;
                    if (!defaultModel) {
                        messaging.notify({
                            title: "No AI Model Available",
                            message: "Please configure an AI model first",
                            type: "warning",
                        });
                        return;
                    }

                    const threadId = await messaging.rpc({
                        model: "llm.thread",
                        method: "create",
                        args: [[
                            {
                                name: `AI Chat for ${this.thread.model} ${this.thread.id}`,
                                model_id: defaultModel.id,
                                provider_id: defaultModel.llmProvider.id,
                                related_thread_model: this.thread.model,
                                related_thread_id: this.thread.id,
                            }
                        ]],
                    });

                    llmThread = messaging.models["Thread"].insert({
                        id: threadId,
                        model: "llm.thread",
                        name: `AI Chat for ${this.thread.model} ${this.thread.id}`,
                        llmModel: defaultModel,
                        llmChat: llmChat,
                        relatedThreadModel: this.thread.model,
                        relatedThreadId: this.thread.id,
                    });
                }

                await llmChat.selectThread(llmThread.id);
                this.update({ is_chatting_with_ai: true });
            } else {
                this.update({ is_chatting_with_ai: false });
            }
        },
    },
});