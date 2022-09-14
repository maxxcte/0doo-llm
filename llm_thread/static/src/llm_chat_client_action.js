/** @odoo-module **/

import { registry } from '@web/core/registry';
import { LLMChatContainer } from '@llm_thread/components/llm_chat_container/llm_chat_container';

// Register the client action
registry.category('actions').add('llm_thread.chat_client_action', LLMChatContainer);
