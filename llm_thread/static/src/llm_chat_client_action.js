/** @odoo-module **/

import { registry } from '@web/core/registry';
import { LLMChat } from '@llm_thread/components/llm_chat/llm_chat';

// Register the client action
registry.category('actions').add('llm_thread.chat_client_action', LLMChat);
