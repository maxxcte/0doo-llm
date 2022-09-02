/** @odoo-module */

import { DiscussContainer } from "@mail/components/discuss_container/discuss_container";
import { registry } from "@web/core/registry";
import { useModels } from '@mail/component_hooks/use_models';
import '@mail/components/discuss/discuss';

export class LLMDiscussComponent extends DiscussContainer {
    /**
     * @override
     */
    setup() {
        console.log('[LLMDiscussComponent] Setting up component');
        useModels();
        super.setup();
        
        // Create a separate discuss instance for LLM
        this.env.services.messaging.modelManager.messagingCreatedPromise.then(async () => {
            console.log('[LLMDiscussComponent] Messaging service initialized');
            const { action } = this.props;
            
            // Create a new discuss view specifically for LLM
            this.discuss = this.messaging.discuss;
            console.log('[LLMDiscussComponent] Got discuss instance:', this.discuss);
            
            // Create the LLM category and update discuss
            const categoryLLM = this.messaging.models['DiscussSidebarCategory'].insert({
                discussAsLLM: this.discuss,
                serverStateKey: 'is_discuss_sidebar_category_llm_open',
            });
            console.log('[LLMDiscussComponent] Created LLM category:', categoryLLM);

            this.discuss.update({
                discussView: {
                    actionId: action.id,
                },
                isLLMMode: true, // Enable LLM mode from the start
                categoryLLM, // Set the LLM category
            });
            console.log('[LLMDiscussComponent] Updated discuss with LLM mode');

            // Initialize with LLM threads
            await this.messaging.initializedPromise;
            console.log('[LLMDiscussComponent] Messaging fully initialized');
            
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
                
                console.log('[LLMDiscussComponent] Found LLM threads:', llmThreads.length);
                
                if (llmThreads.length > 0) {
                    console.log('[LLMDiscussComponent] Opening first LLM thread:', llmThreads[0]);
                    this.discuss.openThread(llmThreads[0]);
                } else {
                    console.log('[LLMDiscussComponent] No LLM threads found');
                }
            }
        }).catch(error => {
            console.error('[LLMDiscussComponent] Error during initialization:', error);
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
console.log('[LLMDiscussComponent] Registered client action');