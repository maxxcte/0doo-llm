# -*- coding: utf-8 -*-
{
    'name': 'LLM Mail Message Subtypes',
    'version': '16.0.1.0.0',
    'category': 'Discuss/Tools',
    'summary': 'Defines core mail.message subtypes for LLM interactions.',
    'description': """
Defines the basic mail.message.subtype records (User, Assistant, Tool Result)
used across different LLM modules (like llm_thread, llm_openai) to ensure
consistency and avoid dependency conflicts.

Also provides a base override for message_format to identify these subtypes.
    """,
    'depends': [
        'base',
        'mail',
    ],
    'data': [
        'data/mail_message_subtypes.xml',
    ],
    'installable': True,
    'auto_install': False, # Should be installed as a dependency
    'application': False,
    'license': 'LGPL-3',
}