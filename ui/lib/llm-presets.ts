export type LlmPreset = {
  id: string;
  provider: 'openai' | 'anthropic';
  model: string;
  label: string;
};

export const LLM_PRESETS: LlmPreset[] = [
  { id: 'openai:gpt-4o', provider: 'openai', model: 'gpt-4o', label: 'OpenAI GPT-4o' },
  { id: 'openai:gpt-4o-mini', provider: 'openai', model: 'gpt-4o-mini', label: 'OpenAI GPT-4o Mini' },
  { id: 'anthropic:claude-3-5-sonnet-20240620', provider: 'anthropic', model: 'claude-3-5-sonnet-20240620', label: 'Claude 3.5 Sonnet (2024-06-20)' },
  { id: 'anthropic:claude-3-opus-20240229', provider: 'anthropic', model: 'claude-3-opus-20240229', label: 'Claude 3 Opus' },
];
