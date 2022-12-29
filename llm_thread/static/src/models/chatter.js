/** @odoo-module **/

import { registerPatch } from "@mail/model/model_core";
import { attr, one } from "@mail/model/model_field";
import { clear } from "@mail/model/model_field_command";

console.log("Chatter.js loaded");

registerPatch({
    name: "Chatter",
    fields: {
        is_chatting_with_ai: attr({
            default: false,
        }),
        llmChatThread: one("Thread", {
            compute() {
                console.log("🧵 Computing llmChatThread", {
                    is_chatting_with_ai: this.is_chatting_with_ai,
                    hasThreadView: !!this.llmChatThreadView
                });
                
                if (!this.is_chatting_with_ai || !this.llmChatThreadView) {
                    console.log("❌ Clearing llmChatThread");
                    return clear();
                }
                
                console.log("📄 Found thread:", this.llmChatThreadView.thread);
                return this.llmChatThreadView.thread;
            },
        }),
        llmChatThreadView: one("ThreadView", {
            compute() {
                console.log("🔍 Computing llmChatThreadView", {
                    is_chatting_with_ai: this.is_chatting_with_ai,
                    hasThread: !!this.thread,
                    hasLLMChat: !!this.messaging.llmChat
                });
                
                if (!this.is_chatting_with_ai || !this.thread) {
                    console.log("❌ Clearing llmChatThreadView - basic check failed");
                    return clear();
                }
                
                const llmChat = this.messaging.llmChat;
                if (!llmChat || !llmChat.activeThread || !llmChat.llmChatView) {
                    console.log("❌ Clearing llmChatThreadView - llmChat check failed", {
                        hasActiveThread: !!llmChat?.activeThread,
                        hasLLMChatView: !!llmChat?.llmChatView
                    });
                    return clear();
                }
                
                console.log("✅ Creating ThreadView", {
                    threadViewer: llmChat.llmChatView.threadViewer,
                    activeThread: llmChat.activeThread
                });
                
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
            console.log("🚀 Starting toggleAIChat");
            console.log("Current thread:", this.thread);
            const messaging = this.messaging;
            if (!this.thread) {
                console.log("❌ No thread found, returning");
                return;
            }

            if (!this.is_chatting_with_ai) {
                console.log("📱 Starting AI chat");
                let llmChat = messaging.llmChat;
                console.log("Initial llmChat:", llmChat);
                if (!llmChat) {
                    console.log("🆕 Creating new llmChat");
                    messaging.update({
                        llmChat: {
                            isInitThreadHandled: false,
                        },
                    });
                    llmChat = messaging.llmChat;
                }

                // Ensure llmChatView is initialized
                if (!llmChat.llmChatView) {
                    console.log("🌟 Initializing llmChatView");
                    llmChat.open(); // This sets llmChatView: {}
                }

                console.log("Loading models and threads...");
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
                console.log("Found existing llmThread:", llmThread);

                if (!llmThread) {
                    console.log("Creating new llmThread");
                    const defaultModel = llmChat.defaultLLMModel;
                    console.log("Default LLM Model:", defaultModel);
                    if (!defaultModel) {
                        console.log("❌ No default model found");
                        messaging.notify({
                            title: "No AI Model Available",
                            message: "Please configure an AI model first",
                            type: "warning",
                        });
                        return;
                    }

                    console.log("Creating thread with model:", defaultModel.name);
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
                    console.log("Created new thread with ID:", threadId);

                    llmThread = messaging.models["Thread"].insert({
                        id: threadId,
                        model: "llm.thread",
                        name: `AI Chat for ${this.thread.model} ${this.thread.id}`,
                        llmModel: defaultModel,
                        llmChat: llmChat,
                        relatedThreadModel: this.thread.model,
                        relatedThreadId: this.thread.id,
                    });
                    console.log("Inserted new thread:", llmThread);
                }

                console.log("Selecting thread:", llmThread.id);
                await llmChat.selectThread(llmThread.id);
                console.log("Updating is_chatting_with_ai to true");
                this.update({ is_chatting_with_ai: true });
            } else {
                console.log("Closing AI chat");
                this.update({ is_chatting_with_ai: false });
            }
            console.log("🏁 Finished toggleAIChat", this.is_chatting_with_ai);
        },
    },
});