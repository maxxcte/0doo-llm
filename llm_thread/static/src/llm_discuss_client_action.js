/** @odoo-module */

import { DiscussContainer } from "@mail/components/discuss_container/discuss_container";
import { registry } from "@web/core/registry";
import { useModels } from '@mail/component_hooks/use_models';
import '@mail/components/discuss/discuss';

const { onWillDestroy } = owl;

export class LLMDiscussComponent extends DiscussContainer {
    /**
     * @override
     */
    setup() {
        useModels();
        super.setup();
        onWillDestroy(() => this._willDestroy());
        
        // Create a separate discuss instance for LLM
        this.env.services.messaging.modelManager.messagingCreatedPromise.then(async () => {
            const { action } = this.props;
            
            // Create a new discuss view specifically for LLM
            this.discuss = this.messaging.discuss;
            
            // Create the LLM category and update discuss
            const categoryLLM = this.messaging.models['DiscussSidebarCategory'].insert({
                discussAsLLM: this.discuss,
                name: "LLM Threads",
                serverStateKey: 'is_category_llm_open',
            });

            this.discuss.update({
                discussView: {
                    actionId: action.id,
                },
                isLLMMode: true, // Enable LLM mode from the start
                categoryLLM, // Set the LLM category
            });

            // Initialize with LLM threads
            await this.messaging.initializedPromise;
            if (!this.discuss.isInitThreadHandled) {
                this.discuss.update({ 
                    isInitThreadHandled: true,
                });
                
                // Load LLM threads instead of default inbox
                const llmThreads = this.messaging.models['Thread']
                    .all()
                    .filter(thread => 
                        thread.model === 'llm.thread' &&
                        thread.isPinned
                    )
                    .sort((a, b) => b.lastMessage?.datetime?.unix() - a.lastMessage?.datetime?.unix());
                
                if (llmThreads.length > 0) {
                    this.discuss.openThread(llmThreads[0]);
                }
            }
        });
    }

    /**
     * @override
     */
    get messaging() {
        return this.env.services.messaging.modelManager.messaging;
    }
}

Object.assign(LLMDiscussComponent, {
    props: DiscussContainer.props,
    components: DiscussContainer.components,
    template: DiscussContainer.template,
});

// Register the client action
registry.category("actions").add("llm_thread.action_llm_discuss", LLMDiscussComponent);