/** @odoo-module **/

import { registerModel } from "@mail/model/model_core";
import { attr, one, many } from "@mail/model/model_field";
import { clear } from "@mail/model/model_field_command";

registerModel({
  name: "LLMChat",
  recordMethods: {
    /**
     * Closes the LLM chat and resets its view state.
     */
    close() {
      this.update({ llmChatView: clear() });
    },

    /**
     * Opens the initial thread based on initActiveId or defaults to the first thread.
     */
    openInitThread() {
      if (!this.initActiveId) {
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
      if (!thread && this.threads.length > 0) {
        this.selectThread(this.threads[0].id);
      } else if (thread) {
        this.selectThread(thread.id);
      }
    },

    /**
     * Opens a specific thread in the LLM chat UI.
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
     * Formats a thread into an active ID string.
     * @param {Thread} thread
     * @returns {string}
     */
    threadToActiveId(thread) {
      return `${thread.model}_${thread.id}`;
    },

    /**
     * Loads threads from the server for the current user.
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
     * Selects a thread by ID as the active thread.
     * @param {number} threadId
     */
    async selectThread(threadId) {
      const thread = this.messaging.models["Thread"].findFromIdentifyingData({
        id: threadId,
        model: "llm.thread",
      });
      if (thread) {
        this.update({ activeThread: thread });
      }
    },

    /**
     * Opens the LLM chat view.
     */
    open() {
      this.update({ llmChatView: {} });
    },

    /**
     * Loads LLM models from the server.
     */
    async loadLLMModels() {
      const result = await this.messaging.rpc({
        model: "llm.model",
        method: "search_read",
        kwargs: {
          domain: [],
          fields: ["name", "id", "provider_id", "default"],
        },
      });

      const llmModelData = result.map((model) => ({
        id: model.id,
        name: model.name,
        llmProvider: model.provider_id
          ? { id: model.provider_id[0], name: model.provider_id[1] }
          : undefined,
        default: model.default,
      }));

      this.update({ llmModels: llmModelData });
    },

    /**
     * Creates a new thread with optional related thread info.
     * @param {Object} params - Thread creation parameters
     * @param {string} params.name - Thread name
     * @param {string} [params.relatedThreadModel] - Related thread model
     * @param {number} [params.relatedThreadId] - Related thread ID
     * @returns {Object} The created thread or null if failed
     */
    async createThread({ name, relatedThreadModel, relatedThreadId }) {
      const defaultModel = this.defaultLLMModel;
      if (!defaultModel) {
        this.messaging.notify({
          title: "No LLMModel available",
          message: "Please add a new LLMModel to use this feature",
          type: "warning",
        });
        return null;
      }

      const threadData = {
        name,
        model_id: defaultModel.id,
        provider_id: defaultModel.llmProvider.id,
      };
      if (relatedThreadModel && relatedThreadId) {
        threadData.related_thread_model = relatedThreadModel;
        threadData.related_thread_id = relatedThreadId;
      }

      const threadId = await this.messaging.rpc({
        model: "llm.thread",
        method: "create",
        args: [[threadData]],
      });

      const threadDetails = await this.messaging.rpc({
        model: "llm.thread",
        method: "read",
        args: [[threadId], ["name", "model_id", "provider_id", "write_date"]],
      });

      if (!threadDetails || !threadDetails[0]) {
        return null;
      }

      const thread = this.messaging.models["Thread"].insert({
        id: threadId,
        model: "llm.thread",
        name: threadDetails[0].name,
        message_needaction_counter: 0,
        isServerPinned: true,
        llmModel: defaultModel,
        llmChat: this,
        updatedAt: threadDetails[0].write_date,
        ...(relatedThreadModel && { relatedThreadModel }),
        ...(relatedThreadId && { relatedThreadId }),
      });

      return thread;
    },

    /**
     * Ensures LLM models and threads are loaded, creating a thread if needed.
     * @param {Object} [options] - Optional parameters
     * @param {string} [options.relatedThreadModel] - Related thread model
     * @param {number} [options.relatedThreadId] - Related thread ID
     * @returns {Object} The active or created thread
     */
    async ensureThread({ relatedThreadModel, relatedThreadId } = {}) {
      if (this.llmModels.length === 0) {
        await this.loadLLMModels();
      }
      if (this.threads.length === 0) {
        await this.loadThreads();
      }

      if (relatedThreadModel && relatedThreadId) {
        const existingThread = this.threads.find(
          (thread) =>
            thread.relatedThreadModel === relatedThreadModel &&
            thread.relatedThreadId === relatedThreadId
        );
        if (existingThread) {
          return existingThread;
        }

        const name = `AI Chat for ${relatedThreadModel} ${relatedThreadId}`;
        return await this.createThread({
          name,
          relatedThreadModel,
          relatedThreadId,
        });
      }

      if (this.threads.length > 0) {
        return this.threads[0];
      }

      const name = `New Chat ${new Date().toLocaleString()}`;
      return await this.createThread({ name });
    },

    async createNewThread() {
      const name = `New Chat ${new Date().toLocaleString()}`;
      const thread = await this.createThread({ name });
      this.selectThread(thread.id);
    },

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

      // Then handle initial thread
      if (!this.isInitThreadHandled) {
        this.update({ isInitThreadHandled: true });
        if (!this.activeThread) {
          this.openInitThread();
        }
      }
    },
  },
  fields: {
    activeId: attr({
      compute() {
        return this.activeThread
          ? this.threadToActiveId(this.activeThread)
          : clear();
      },
    }),
    llmChatView: one("LLMChatView", { inverse: "llmChat", isCausal: true }),
    isInitThreadHandled: attr({ default: false }),
    initActiveId: attr({ default: null }),
    activeThread: one("Thread", { inverse: "activeLLMChat" }),
    threads: many("Thread", { inverse: "llmChat" }),
    orderedThreads: many("Thread", {
      compute() {
        if (!this.threads) return clear();
        return this.threads.slice().sort((a, b) => {
          const dateA = a.updatedAt
            ? new Date(a.updatedAt.replace(" ", "T"))
            : new Date(0);
          const dateB = b.updatedAt
            ? new Date(b.updatedAt.replace(" ", "T"))
            : new Date(0);
          return dateB - dateA;
        });
      },
    }),
    threadCache: one("ThreadCache", {
      compute() {
        return this.activeThread ? { thread: this.activeThread } : clear();
      },
    }),
    llmModels: many("LLMModel"),
    llmProviders: many("LLMProvider", {
      compute() {
        if (!this.llmModels) return clear();
        const providersMap = new Map();
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
        return Array.from(providersMap.values());
      },
    }),
    defaultLLMModel: one("LLMModel", {
      compute() {
        if (!this.llmModels) return clear();
        return (
          this.llmModels.find((model) => model.default) ||
          this.llmModels[0] ||
          clear()
        );
      },
    }),
  },
});
