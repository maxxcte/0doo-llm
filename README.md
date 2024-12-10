# Odoo LLM Integration

![Banner](llm/static/description/banner.jpeg)

This repository provides a comprehensive framework for integrating Large Language Models (LLMs) into Odoo. It allows seamless interaction with various AI providers including OpenAI, Anthropic, Ollama, and Replicate, enabling chat completions, text embeddings, and more within your Odoo environment.

## 🚀 Features

- **Multiple LLM Provider Support**: Connect to OpenAI, Anthropic, Ollama, Mistral, Replicate, and LiteLLM proxy.
- **Unified API**: Consistent interface for all LLM operations regardless of the provider.
- **Chat UI**: Modern, responsive interface with real-time message streaming.
- **Thread Management**: Organize and manage AI conversations effectively.
- **Model Management**: Configure and utilize different models for various tasks.
- **Knowledge Base (RAG)**: Store, index, and retrieve documents for Retrieval-Augmented Generation.
- **Vector Store Integrations**: Supports ChromaDB, pgvector, and Qdrant for efficient similarity searches.
- **Tool Use Framework**: Allows LLMs to use tools to interact with Odoo data and perform actions.
- **AI Assistants**: Build and manage specialized AI assistants with custom instructions and tools.
- **Prompt Management**: Create, manage, and reuse prompts for consistent interactions.
- **Security**: Role-based access control and secure API key management.

## 📦 Modules

| Module                     | Description                                                              |
|----------------------------|--------------------------------------------------------------------------|
| `llm`                      | Base module with core functionality and provider framework               |
| `llm_anthropic`            | Anthropic (Claude) provider integration                                |
| `llm_assistant`            | Assistant management for specialized AI agents with custom tools         |
| `llm_chroma`               | ChromaDB vector store integration                                        |
| `llm_document_page`        | Integration with document pages (e.g., knowledge articles)               |
| `llm_knowledge`            | Core knowledge base functionality (embedding, storage, retrieval)        |
| `llm_knowledge_automation` | Automation rules related to knowledge base processing                    |
| `llm_knowledge_llama`      | LlamaIndex integration for knowledge base functionality (tentative)      |
| `llm_knowledge_mistral`    | Mistral-specific features for knowledge base (tentative)                 |
| `llm_litellm`              | LiteLLM proxy for centralized model management                           |
| `llm_mail_message_subtypes`| LLM integration for mail message subtypes (e.g., summarization)          |
| `llm_mcp`                  | Model Context Protocol Support                                          |
| `llm_mistral`              | Mistral AI provider integration                                          |
| `llm_ollama`               | Ollama provider for local model deployment                               |
| `llm_openai`               | OpenAI (GPT) provider integration                                        |
| `llm_pgvector`             | pgvector (PostgreSQL) vector store integration                           |
| `llm_prompt`               | Management and templating of prompts                                     |
| `llm_qdrant`               | Qdrant vector store integration                                          |
| `llm_replicate`            | Replicate.com provider integration                                       |
| `llm_resource`             | Management of LLM-related resources (e.g., models, configurations)     |
| `llm_store`                | Abstraction layer for vector stores                                      |
| `llm_thread`               | Chat threads and conversation management                                 |
| `llm_tool`                 | Framework for LLM tools (allowing LLMs to interact with Odoo)          |
| `llm_tool_knowledge`       | Tool for LLMs to query the knowledge base                                |

## 🛠️ Installation

1. Clone this repository into your Odoo addons directory:
   ```bash
   git clone https://github.com/apexive/odoo-llm
   ```

2. Install required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Install the base module and desired provider modules through the Odoo Apps menu

## ⚙️ Configuration

After installation:

1. Navigate to LLM → Configuration → Providers
2. Create a new provider with your API credentials
3. Set up models for the provider (can be done automatically using "Fetch Models")
4. Grant appropriate access rights to users

## 🔄 LLM Tools: Building AI-Driven ERP

We're seeing tremendous potential by integrating reasoning/assistant models like ChatGPT, Claude, and others into Odoo. These models can query the Odoo database via functions and interact with server actions for data manipulation.

### Why This Matters

This approach has the potential to revolutionize how users interact with Odoo:
- AI-driven automation of repetitive tasks
- Smart querying & decision-making inside Odoo
- A flexible ecosystem for custom AI assistants

### Help Wanted - Let's Build This Together!

We are committed to keeping this project truly open source and building an open AI layer for Odoo ERP that benefits everyone. We're looking for contributions in these areas:

- Unit tests & CI/CD
- Security & access control improvements
- Multi-model support enhancement
- Localization & translations
- Documentation and examples

## 🤝 Contributing

We welcome contributions! Here's how you can help:

1. **Issues**: Report bugs or suggest features through the Issues tab
2. **Discussions**: Join conversations about development priorities and approaches
3. **Pull Requests**: Submit code contributions for fixes or new features

### Guidelines

- Follow the existing code style and structure
- Write clean, well-documented code
- Include tests for new functionality
- Update documentation as necessary

## 🔮 Roadmap

- [x] Enhanced RAG (Retrieval Augmented Generation) capabilities (Foundation built, further enhancements planned)
- [x] Function calling support for model-driven actions (Framework exists via `llm_tool`, expansion planned)
- [ ] Multi-modal content handling (images, audio)
- [x] Advanced prompt templates and management (Basic management via `llm_prompt`, advanced features planned)
- [ ] Integration with other Odoo modules (CRM, HR, etc.)
- [x] Improving assistant frameworks for complex task automation (Foundation via `llm_assistant`, improvements planned)

## 📜 License

This project is licensed under LGPL-3 - see the LICENSE file for details.

## 🌐 About

Developed by [Apexive](https://apexive.com) - We're passionate about bringing advanced AI capabilities to the Odoo ecosystem.

For questions, support, or collaboration opportunities, please open an issue or discussion in this repository.
