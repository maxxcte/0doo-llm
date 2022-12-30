/** @odoo-module **/

import { registerModel } from "@mail/model/model_core";
import { attr, one, many } from "@mail/model/model_field";
import { clear } from "@mail/model/model_field_command";

registerModel({
  name: "LLMChat",
  recordMethods: {
    /**
     * Close the LLM chat. Should reset its internal state.
     */
    close() {
      this.update({ llmChatView: clear() });
    },

    /**
     * Opens thread from init active id if the thread exists.
     */
    openInitThread() {
      if (!this.initActiveId) {
        // If no initial thread specified, select the first thread
        if (this.threads.length > 0) {
          this.selectThread(this.threads[0].id);
        }
        return;
      }

      const [model, id] =
        typeof this.initActiveId === "number"
          ? ["llm.thread", this.initActiveId]
          : this.initActiveId.split("_");
      const thread = this.messaging.models["Thread"].findFromIdentifyingData({
        id: Number(id),
        model,
      });
      if (!thread) {
        // If specified thread not found, select first thread
        if (this.threads.length > 0) {
          this.selectThread(this.threads[0].id);
        }
        return;
      }
      this.selectThread(thread.id);
    },

    /**
     * Opens the given thread in LLMChat
     *
     * @param {Thread} thread
     */
    async openThread(thread) {
      this.update({ thread });
      if (!this.llmChatView) {
        this.env.services.action.doAction("llm_thread.action_llm_chat", {
          name: this.env._t("Chat"),
          active_id: this.threadToActiveId(thread),
          clearBreadcrumbs: false,
        });
      }
    },

    /**
     * @param {Thread} thread
     * @returns {string}
     */
    threadToActiveId(thread) {
      return `${thread.model}_${thread.id}`;
    },

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
          ],
          order: "write_date desc",
        },
      });

      // Convert results to Thread records
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

      // Update threads in the store
      this.update({ threads: threadData });
    },
    /**
     * @param {integer} threadId
     */
    async selectThread(threadId) {
      const thread = this.messaging.models["Thread"].findFromIdentifyingData({
        id: threadId,
        model: "llm.thread",
      });

      if (thread) {
        // Update active thread - ThreadCache will handle message loading
        this.update({ activeThread: thread });
      }
    },

    open() {
      this.update({ llmChatView: {} });
    },

    async loadLLMModels() {
      const result = await this.messaging.rpc({
        model: "llm.model",
        method: "search_read",
        kwargs: {
          domain: [],
          fields: ["name", "id", "provider_id", "default"],
        },
      });

      // Convert results to LLMModel records
      const llmModelData = result.map((model) => ({
        id: model.id,
        name: model.name,
        llmProvider: model.provider_id
          ? { id: model.provider_id[0], name: model.provider_id[1] }
          : undefined,
        default: model.default,
      }));

      // Update llmModels in the store
      this.update({ llmModels: llmModelData });
    },
    async createNewThread() {
      // Get the default model or first available model
      const defaultModel = this.defaultLLMModel;
      if (!defaultModel) {
        this.messaging.notify({
          title: "No LLMModel available",
          message: "Please add a new LLMModel to use this feature",
          type: "warning",
        });
        return;
      }
      const threadName = `New Chat ${new Date().toLocaleString()}`;
      // Create new thread via RPC
      const threadId = await this.messaging.rpc({
        model: "llm.thread",
        method: "create",
        args: [
          [
            {
              model_id: defaultModel.id,
              provider_id: defaultModel.llmProvider.id,
              name: threadName,
            },
          ],
        ],
      });

      const threadDetails = await this.messaging.rpc({
        model: "llm.thread",
        method: "read",
        args: [[threadId], ["name", "model_id", "provider_id", "write_date"]],
      });
      if (!threadDetails || !threadDetails[0]) {
        return;
      }

      // Insert the thread into frontend models
      await this.messaging.models["Thread"].insert({
        id: threadId,
        model: "llm.thread",
        name: threadDetails[0].name,
        message_needaction_counter: 0,
        isServerPinned: true,
        llmModel: defaultModel,
        llmChat: this,
        updatedAt: threadDetails[0].write_date,
      });
      this.selectThread(threadId);
    },
  },
  fields: {
    /**
     * Formatted active id of the current thread
     */
    activeId: attr({
      compute() {
        if (!this.activeThread) {
          return clear();
        }
        return this.threadToActiveId(this.activeThread);
      },
    }),
    /**
     * View component for this LLMChat
     */
    llmChatView: one("LLMChatView", {
      inverse: "llmChat",
      isCausal: true,
    }),
    /**
     * Determines if the logic for opening a thread via the `initActiveId`
     * has been processed.
     */
    isInitThreadHandled: attr({
      default: false,
    }),
    /**
     * Formatted init thread on opening chat for the first time
     * Format: <threadModel>_<threadId>
     */
    initActiveId: attr({
      default: null,
    }),
    /**
     * Currently active thread
     */
    activeThread: one("Thread", {
      inverse: "activeLLMChat",
    }),
    /**
     * All threads in this chat
     */
    threads: many("Thread", {
      inverse: "llmChat",
    }),
    orderedThreads: many("Thread", {
      compute() {
        if (!this.threads) {
          return clear();
        }
        const sortedThreads = this.threads.slice().sort((a, b) => {
          const dateA = a.updatedAt
            ? new Date(a.updatedAt.replace(" ", "T"))
            : new Date(0);
          const dateB = b.updatedAt
            ? new Date(b.updatedAt.replace(" ", "T"))
            : new Date(0);
          return dateB - dateA;
        });
        return sortedThreads;
      },
    }),
    threadCache: one("ThreadCache", {
      compute() {
        if (!this.activeThread) {
          return clear();
        }
        return {
          thread: this.activeThread,
        };
      },
    }),
    llmModels: many("LLMModel"),
    llmProviders: many("LLMProvider", {
      compute() {
        if (!this.llmModels) {
          return clear();
        }
        // Create a map to track unique providers by ID
        const providersMap = new Map();

        // Extract unique providers from llmModels' data
        for (const model of this.llmModels) {
          const providerId = model.llmProvider?.id;
          const providerName = model.llmProvider?.name;
          if (providerId && !providersMap.has(providerId)) {
            providersMap.set(providerId, {
              id: providerId,
              name: providerName,
            });
          }
        }

        // Convert map values to array
        return Array.from(providersMap.values());
      },
    }),
    defaultLLMModel: one("LLMModel", {
      compute() {
        if (!this.llmModels) {
          return clear();
        }
        return (
          this.llmModels.find((model) => model.default) ||
          this.llmModels[0] ||
          clear()
        );
      },
    }),
  },
});
