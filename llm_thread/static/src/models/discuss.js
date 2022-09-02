/** @odoo-module **/
import { registerPatch } from '@mail/model/model_core';

registerPatch({
    name: 'Discuss',
    fields: {
        // Add new field to control LLM mode
        isLLMMode: attr({
            default: false,
        }),
        // Override orderedCategories to show only LLM category in LLM mode
        orderedCategories: {
            compute() {
                if (this.isLLMMode) {
                    return this.categoryLLM ? [this.categoryLLM] : [];
                }
                return this._super();
            }
        },
        // Add LLM category
        categoryLLM: one('DiscussSidebarCategory', {
            compute() {
                if (!this.discussView || !this.isLLMMode) {
                    return clear();
                }
                return this.messaging.models['DiscussSidebarCategory'].insert({
                    discussViewOwner: this.discussView,
                    serverStateKey: 'is_category_llm_open',
                    name: "LLM Threads",
                });
            }
        })
    }
});

// Patch DiscussSidebarCategory to handle LLM threads
registerPatch({
    name: 'DiscussSidebarCategory',
    fields: {
        categoryItems: {
            compute() {
                const discuss = this.discussViewOwner.discuss;
                if (discuss.isLLMMode && discuss.categoryLLM === this) {
                    return this.messaging.models['Thread']
                        .all()
                        .filter(thread => 
                            thread.model === 'llm.thread' &&
                            thread.isPinned
                        )
                        .map(thread => 
                            this.messaging.models['DiscussSidebarCategoryItem'].insert({
                                category: this,
                                thread,
                            })
                        );
                }
                return this._super();
            }
        }
    }
});