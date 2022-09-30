/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { attr, one } from '@mail/model/model_field';
import { markdownToHtml } from '../utils/markdown_utils';
import { registry } from '@web/core/registry'
const rpc = registry.category("services").get("rpc");

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
        // computed field from streaming content
        htmlStreamingContent: attr({
            compute() {
                return markdownToHtml(this.streamingContent);
            },
        }),
    },
    recordMethods: {
        /**
         * Post AI message to the thread
         * @private
         */
        async _postAIMessage(body) {
            const params = {
                thread_model: 'llm.thread',  // Your model name
                thread_id: this.id,   // Your thread ID
                post_data: {
                    body,
                    author_id: false,
                    email_from: "ai@apexive.com",
                },
            }
            let messageData = await this.messaging.rpc({ route: `/mail/message/post`, params });
            console.log(messageData);
        },
        /**
         * Stop streaming response for this thread
         */
        async _stopStreaming(eventSource) {
            if (!this.isStreaming) {
                return;
            }
            this.update({ isStreaming: false, streamingContent: '' });
            eventSource.close();
        },
        /**
         * Start streaming response for this thread
         */
        async startStreaming() {
            if (this.isStreaming) {
                return;
            }
            
            this.update({ isStreaming: true, streamingContent: '' });
            const eventSource = new EventSource(`/llm/thread/stream_response?thread_id=${this.id}`);
            
            eventSource.onmessage = async (event) => {
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
                        // Post the final message
                        await this._postAIMessage(this.htmlStreamingContent);
                        this._stopStreaming(eventSource);
                        break;
                }
            };
            
            eventSource.onerror = (error) => {
                console.error('EventSource failed:', error);
                this._stopStreaming(eventSource);
            };
        },
    },
});
