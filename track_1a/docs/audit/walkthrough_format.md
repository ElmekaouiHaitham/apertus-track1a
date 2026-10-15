# Walkthrough representation

The findings use `<|user_start|> ... <|user_end|>` and
`<|assistant_start|> ... <|assistant_end|>`, consistent with the role delimiters
in the public `swiss-ai/Apertus-v1.5-70B` processor `chat_template.jinja`
checked on 14 October 2026. The exact API prompt and response are inserted
verbatim between those delimiters.

This is a reconstruction of exposed API messages, not a captured native token
stream. No BOS token, default system instructions, hidden reasoning or server
configuration has been invented. The hosted checkpoint revision/system text
were unreported; the public template does not establish what the provider used.

Source: https://huggingface.co/swiss-ai/Apertus-v1.5-70B/blob/main/chat_template.jinja
