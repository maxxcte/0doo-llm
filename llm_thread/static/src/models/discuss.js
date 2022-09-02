/** @odoo-module **/
import { registerPatch } from '@mail/model/model_core';
import { attr, one } from '@mail/model/model_field';
import { clear } from '@mail/model/model_field_command';

registerPatch({
    name: 'Discuss',
    fields: {
        isLLMMode: attr({
            default: false,
        }),
        categoryLLM: one('DiscussSidebarCategory', {
            default: {},
            inverse: 'discussAsLLM',
        }),
        activeThread: {
            compute() {
                if (!this.thread) {
                    return clear();
                }
                if (this.isLLMMode) {
                    if (this.thread.model === 'llm.thread' && this.thread.isPinned) {
                        return this.thread;
                    }
                    return clear();
                }
                return this._super();
            }
        }
    }
});

// Patch DiscussSidebarCategory to handle LLM threads
registerPatch({
    name: 'DiscussSidebarCategory',
    fields: {
        discussAsLLM: one('Discuss', {
            identifying: true,
            inverse: 'categoryLLM',
        }),
        name: {
            compute() {
                if (this.discussAsLLM) {
                    return this.env._t("LLM Threads");
                }
                return this._super();
            }
        },
        supportedChannelTypes: {
            compute() {
                if (this.discussAsLLM) {
                    return ['llm_thread'];
                }
                return this._super();
            }
        },
        autocompleteMethod: {
            compute() {
                if (this.discussAsLLM) {
                    return 'llm_thread';
                }
                return this._super();
            }
        },
        hasAddCommand: {
            compute() {
                if (this.discussAsLLM) {
                    return true;
                }
                return this._super();
            }
        },
        hasViewCommand: {
            compute() {
                if (this.discussAsLLM) {
                    return false;
                }
                return this._super();
            }
        },
        serverStateKey: {
            compute() {
                if (this.discussAsLLM) {
                    return 'is_discuss_sidebar_category_llm_open';
                }
                return this._super();
            }
        },
        orderedCategoryItems: {
            compute() {
                if (this.discussAsLLM) {
                    return this.categoryItemsOrderedByLastAction;
                }
                return this._super();
            }
        },
        categoryItemsOrderedByLastAction: {
            compute() {
                if (this.discussAsLLM) {
                    return this.categoryItems;
                }
                return this._super();
            }
        },
        commandAddTitleText: {
            compute() {
                if (this.discussAsLLM) {
                    return this.env._t("Start an LLM Thread");
                }
                return this._super();
            }
        },
        newItemPlaceholderText: {
            compute() {
                if (this.discussAsLLM) {
                    return this.env._t("Find or start an LLM thread...");
                }
                return this._super();
            }
        },
        isServerOpen: {
            compute() {
                if (!this.messaging.currentUser || !this.messaging.currentUser.res_users_settings_id) {
                    return clear();
                }
                if (this.discussAsLLM) {
                    return this.messaging.currentUser.res_users_settings_id.is_discuss_sidebar_category_llm_open;
                }
                return this._super();
            }
        }
    }
});