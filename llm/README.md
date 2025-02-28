# LLM Integration Base for Odoo

Connect your Odoo instance with leading AI providers like OpenAI, Anthropic, Replicate and more. This base module enables chat completions, text embeddings, and model management for Odoo.

## Overview

LLM Integration Base provides a unified framework for connecting various AI providers and models with your Odoo instance. This module serves as the foundation for building AI-powered features across your Odoo applications.

### Core Capabilities

- **Chat completions** - Generate conversational responses
- **Text embeddings** - Create vector representations of text
- **Model management** - Organize and configure LLM models
- **Tool support framework** - Enable function calling capabilities

## Key Features

- **Multiple Provider Support**: Connect with OpenAI, Anthropic Claude, Ollama, Replicate, and more AI providers through a unified interface
- **Model Discovery**: Automatically discover and import available models from connected providers
- **Publisher Management**: Track model publishers, organizations, and their official status
- **Secure API Storage**: Safely store API keys and endpoint configurations for each provider
- **Role-Based Security**: Control access to LLM features with dedicated security groups and record rules
- **Tool Execution Framework**: Enable AI models to execute functions through a standardized interface

## Getting Started

### Installation

1. Download the module from [GitHub](https://github.com/apexive/odoo-llm)
2. Install the module in your Odoo instance
3. Verify the dependencies are satisfied (`mail`, `web`)

### Configuration

1. Navigate to **LLM > Configuration > Providers**
2. Create a new provider and select the service type
3. Enter your API key and base URL (if required)
4. Click "Fetch Models" to import available models
5. Set default models for chat, embedding, and other services

## Supported AI Providers

The LLM Integration Base works with multiple AI providers through dedicated modules:

- **llm_openai**: OpenAI integration (GPT-4, GPT-3.5, etc.)
- **llm_anthropic**: Anthropic Claude integration
- **llm_ollama**: Local Ollama server integration
- **llm_mistral**: Mistral AI integration
- **llm_litellm**: Multi-provider support through LiteLLM
- **llm_replicate**: Replicate platform integration

Additional provider modules may be available in the repository. The modular architecture makes it easy to add support for additional providers.

## OpenAI-Compatible Endpoints

Many providers offer OpenAI-compatible endpoints, making it easy to switch between different AI services without changing your code. The module supports these standardized endpoints, allowing you to use the same integration patterns across different providers.

The modular architecture makes it easy to add support for additional providers. Check our [GitHub repository](https://github.com/apexive/odoo-llm) for the latest provider implementations.

## Related Modules

The LLM Integration Base is part of a comprehensive AI ecosystem for Odoo. Explore these additional modules for enhanced functionality:

- **Easy AI Chat**: A simple, powerful AI chat module to supercharge your Odoo workflows with real-time conversations
- **LLM Assistant**: Create and manage specialized AI assistants with dedicated tools and configurations
- **LLM RAG (Retrieval Augmented Generation)**: Enhance AI responses with knowledge from your Odoo database
- **LLM Tool**: Implement function calling capabilities for AI models

## Technical Specifications

### Module Information

- **Name**: LLM Integration Base
- **Version**: 16.0.1.1.0
- **Category**: Technical
- **License**: LGPL-3
- **Dependencies**: mail, web
- **Author**: Apexive Solutions LLC

### Key Models

- **llm.provider**: Manages connections to AI providers
- **llm.model**: Represents individual AI models
- **llm.publisher**: Tracks organizations that publish models
- **llm.fetch.models.wizard**: Wizard for importing models from providers

## Support & Resources

- **Documentation**: Find detailed documentation, examples, and integration guides in our [GitHub repository](https://github.com/apexive/odoo-llm)
- **Community & Support**: Join our community to get help, share ideas, and contribute to the development of the LLM integration ecosystem for Odoo
  - [Report Issues](https://github.com/apexive/odoo-llm/issues)
  - [Feature Requests](https://github.com/apexive/odoo-llm)

## License

This module is licensed under [LGPL-3](https://www.gnu.org/licenses/lgpl-3.0.html).

---

2025 Apexive Solutions LLC. All rights reserved.
