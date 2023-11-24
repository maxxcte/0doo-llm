16.0.1.1.2 (2025-04-08)
~~~~~~~~~~~~~~~~~~~~~~~

* [IMP] Added workaround for Gemini API compatibility (generates placeholder `tool_call_id` if missing)
* [IMP] Modified message formatting to conditionally include `content` key for Gemini compatibility
* [FIX] Fixed errors when using Gemini API due to missing `tool_call_id`

16.0.1.1.1 (2025-04-03)
~~~~~~~~~~~~~~~~~~~~~~~

* [FIX] Added default model for OpenAI, will work when user adds API key

16.0.1.1.0 (2025-03-06)
~~~~~~~~~~~~~~~~~~~~~~~

* [ADD] Tool support for OpenAI models - Implemented function calling capabilities
* [IMP] Enhanced message handling for tool execution
* [IMP] Added support for processing tool results in chat context

16.0.1.0.0 (2025-01-02)
~~~~~~~~~~~~~~~~~~~~~~~

* [INIT] Initial release of the module
