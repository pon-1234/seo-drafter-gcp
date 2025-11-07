export type LlmPreset = {
  id: string;
  provider: 'openai' | 'anthropic';
  model: string;
  label: string;
};

export const LLM_PRESETS: LlmPreset[] = [
  { id: 'openai:gpt-5', provider: 'openai', model: 'gpt-5', label: 'OpenAI GPT-5' },
  { id: 'openai:gpt-5-mini', provider: 'openai', model: 'gpt-5-mini', label: 'OpenAI GPT-5 Mini' },
  { id: 'openai:o4-mini', provider: 'openai', model: 'o4-mini', label: 'OpenAI o4-mini' },
  { id: 'anthropic:claude-sonnet-4-5', provider: 'anthropic', model: 'claude-sonnet-4-5', label: 'Claude Sonnet 4.5' },
  { id: 'anthropic:claude-sonnet-4-5-20250929', provider: 'anthropic', model: 'claude-sonnet-4-5-20250929', label: 'Claude Sonnet 4.5 (2025-09-29 snapshot)' },
  { id: 'anthropic:claude-haiku-4-5', provider: 'anthropic', model: 'claude-haiku-4-5', label: 'Claude Haiku 4.5' },
  { id: 'anthropic:claude-opus-4-1', provider: 'anthropic', model: 'claude-opus-4-1', label: 'Claude Opus 4.1' },
];
