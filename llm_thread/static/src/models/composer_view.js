/** @odoo-module **/

import { registerPatch } from '@mail/model/model_core';
import { attr } from '@mail/model/model_field';
import { markdownToHtml } from '../utils/markdown_utils';

registerPatch({
    name: "ComposerView",
    fields: {
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
            const composer = this.composer;
            const params = {
                thread_id: composer.thread.id,
                body,
            }
            const messaging = this.messaging;
            let messageData = await messaging.rpc({ route: `/llm/thread/post_ai_response`, params }, { shadow: true });
            if (!messaging.exists()) {
                return;
            }
            const message = messaging.models['Message'].insert(
                messaging.models['Message'].convertData(messageData)
            );
            if (messaging.hasLinkPreviewFeature && !message.isBodyEmpty) {
                messaging.rpc({
                    route: `/mail/link_preview`,
                    params: {
                        message_id: message.id
                    }
                }, { shadow: true });
            }
            for (const threadView of message.originThread.threadViews) {
                // Reset auto scroll to be able to see the newly posted message.
                threadView.update({ hasAutoScrollOnMessageReceived: true });
                threadView.addComponentHint('message-posted', { message });
            }
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
            const defaultContent = 'Thinking...';
            if (this.isStreaming) {
                return;
            }
            const composer = this.composer;
            
            this.update({ isStreaming: true, streamingContent: defaultContent });
            const eventSource = new EventSource(`/llm/thread/stream_response?thread_id=${composer.thread.id}`);
            
            eventSource.onmessage = async (event) => {
                const data = JSON.parse(event.data);
                switch (data.type) {
                    case 'start':
                        break;
                    case 'content':
                        if (this.streamingContent === defaultContent) {
                            this.update({ streamingContent: '' });
                        }
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
                        const htmlStreamingContent = this.htmlStreamingContent;
                        await this._postAIMessage(htmlStreamingContent);
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
