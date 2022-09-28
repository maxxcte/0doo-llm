/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { attr, one } from '@mail/model/model_field';

registerPatch({
    name: 'Thread',
    fields: {
        llmChat: one('LLMChat', {
            inverse: 'threads',
        }),
        activeLLMChat: one('LLMChat', {
            inverse: 'activeThread',
        }),
        // Streaming related fields
        isStreaming: attr({
            default: false,
        }),
        streamingContent: attr({
            default: '',
        }),
    },
    recordMethods: {
        /**
         * Start streaming response for this thread
         */
        async startStreaming() {
            if (this.isStreaming) {
                return;
            }
            
            this.update({ isStreaming: true, streamingContent: '' });
            const eventSource = new EventSource(`/llm/thread/stream_response?thread_id=${this.id}`);
            
            eventSource.onmessage = (event) => {
                const data = JSON.parse(event.data);
                switch (data.type) {
                    case 'start':
                        this.update({ streamingContent: '' });
                        break;
                    case 'content':
                        this.update({ 
                            streamingContent: this.streamingContent + (data.content || ''),
                        });
                        break;
                    case 'error':
                        console.error('Streaming error:', data.error);
                        eventSource.close();
                        this.update({ isStreaming: false });
                        break;
                    case 'end':
                        eventSource.close();
                        this.update({ isStreaming: false, streamingContent: '' });
                        break;
                }
            };
            
            eventSource.onerror = (error) => {
                console.error('EventSource failed:', error);
                eventSource.close();
                this.update({ isStreaming: false });
            };
        },
    },
});
