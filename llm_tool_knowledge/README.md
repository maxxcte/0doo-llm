# LLM Tool RAG

This module extends the core RAG (Retrieval Augmented Generation) functionality in Odoo with specialized tools for knowledge retrieval, document search, and more.

## Overview

LLM Tool RAG provides a set of AI-powered tools that enable Large Language Models to access and utilize your organization's knowledge base for more accurate and context-aware responses.

## Features

- **Knowledge Retriever**: Retrieve relevant information from your document database using semantic search
- **Document Search**: Advanced search capabilities for document chunks
- **Function Calling**: Enable AI models to execute specific functions
- **Integration with RAG**: Seamless integration with the core RAG module

## Installation

1. Install the base `llm` and `llm_rag` modules
2. Install this module (`llm_tool_rag`)
3. Configure your tools in the LLM settings

## Technical Details

The module is built on Odoo's model system and extends the following models:

- `llm.tool` - Base model for all LLM tools
- `llm.document.search.mixin` - Mixin for document search functionality

## Security

The module follows Odoo's standard security model:

- Regular users (base.group_user) have read-only access
- LLM Managers (llm.group_llm_manager) have full CRUD access

## Dependencies

- base
- mail
- llm
- llm_rag

## License

LGPL-3

## Author

Mpve Solutions LLC
