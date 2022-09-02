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
        this.env.services.messaging.modelManager.messagingCreatedPromise.then(async () => {
            const { action } = this.props;
            // Use LLM thread as default if not specified
            const initActiveId = 
                (action.context && action.context.active_id) ||
                (action.params && action.params.default_active_id) ||
                'llm.thread';
            
            this.discuss = this.messaging.discuss;
            this.discuss.update({
                discussView: {
                    actionId: action.id,
                },
                initActiveId,
                isLLMMode: true,
            });

            await this.messaging.initializedPromise;
            if (!this.discuss.isInitThreadHandled) {
                this.discuss.update({ isInitThreadHandled: true });
                if (!this.discuss.activeThread) {
                    this.discuss.openInitThread();
                }
            }
        });
        
        LLMDiscussComponent.currentInstance = this;
    }

    get messaging() {
        return this.env.services.messaging.modelManager.messaging;
    }

    _willDestroy() {
        if (this.discuss && LLMDiscussComponent.currentInstance === this) {
            this.discuss.close();
        }
    }
}

Object.assign(LLMDiscussComponent, {
    props: DiscussContainer.props,
    components: DiscussContainer.components,
    template: DiscussContainer.template,
});

// Register the client action
registry.category("actions").add("llm_thread.action_llm_discuss", LLMDiscussComponent);