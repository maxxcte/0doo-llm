/** @odoo-module **/

import { registerPatch } from "@mail/model/model_core";
import { many } from "@mail/model/model_field";

registerPatch({
    name: "LLMChat",
    fields: {
        tools: many("LLMTool"),
    },
    recordMethods: {
        /**
         * Load tools from the server
         */
        async loadTools() {
            try {
                const result = await this.messaging.rpc({
                    model: "llm.tool",
                    method: "search_read",
                    kwargs: {
                        domain: [["active", "=", true]],
                        fields: ["name", "id"],
                    },
                });

                const toolData = result.map((tool) => ({
                    id: tool.id,
                    name: tool.name,
                }));

                this.update({ tools: toolData });
            } catch (error) {
                console.error("Error loading tools:", error);
                return [];
            }
        },
        
        /**
         * Extended version of ensureThread to load tools
         * @override
         */
        async ensureThread(options = {}) {
            // Call the original method first
            const thread = await this._super(options);
            
            // Load tools if not already loaded
            if (!this.tools || this.tools.length === 0) {
                await this.loadTools();
            }
            
            return thread;
        },
        
        /**
         * Extended version of loadThreads to include tool_ids
         * @override
         */
        async loadThreads() {
            const result = await this.messaging.rpc({
                model: "llm.thread",
                method: "search_read",
                kwargs: {
                    domain: [["create_uid", "=", this.env.services.user.userId]],
                    fields: [
                        "name",
                        "message_ids",
                        "create_uid",
                        "create_date",
                        "write_date",
                        "model_id",
                        "provider_id",
                        "related_thread_model",
                        "related_thread_id",
                        "tool_ids",
                    ],
                    order: "write_date desc",
                },
            });

            const threadData = result.map((thread) => ({
                id: thread.id,
                model: "llm.thread",
                name: thread.name,
                message_needaction_counter: 0,
                creator: thread.create_uid ? { id: thread.create_uid } : undefined,
                isServerPinned: true,
                updatedAt: thread.write_date,
                relatedThreadModel: thread.related_thread_model,
                relatedThreadId: thread.related_thread_id,
                selectedToolIds: thread.tool_ids || [],
                llmModel: thread.model_id
                    ? {
                        id: thread.model_id[0],
                        name: thread.model_id[1],
                        llmProvider: {
                            id: thread.provider_id[0],
                            name: thread.provider_id[1],
                        },
                    }
                    : undefined,
            }));

            this.update({ threads: threadData });
        },
        /**
         * Extended version of loadThreads to include tool_ids
         * @override
         */
        async initializeLLMChat(action, initActiveId) {
            this.update({
              llmChatView: {
                actionId: action.id,
              },
              initActiveId,
            });
      
            // Wait for messaging to be initialized
            await this.messaging.initializedPromise;
            await this.loadLLMModels();
            // Load threads first
            await this.loadThreads();
            await this.loadTools();
      
            // Then handle initial thread
            if (!this.isInitThreadHandled) {
              this.update({ isInitThreadHandled: true });
              if (!this.activeThread) {
                this.openInitThread();
              }
            }
          }
    },
});