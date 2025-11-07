'use client';

import { FormEvent, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { apiFetch } from '@/lib/api';
import { LLM_PRESETS } from '@/lib/llm-presets';

const CLIENT_NG_PHRASES = [
  '計り知れ',
  '魔法のよう',
  '姿が見えるでしょうか',
  '比類ない',
  '驚異的',
  '劇的に改善'
];

const CLIENT_ABSTRACT_PATTERNS = [
  '設定した条件',
  '自動で料金を調整',
  '競争力を維持',
  '最適化されていきます',
  'すべてを改善',
  '高い効果が期待できます'
];

type RewriteResponsePayload = {
  rewritten_text: string;
  detected_ng_phrases: string[];
  detected_abstract_phrases: string[];
};

type DetectionSummary = {
  ng: string[];
  abstract: string[];
};

const detectPhrases = (text: string): DetectionSummary => {
  const hits = (phrases: string[]) => phrases.filter((phrase) => phrase && text.includes(phrase));
  return {
    ng: hits(CLIENT_NG_PHRASES),
    abstract: hits(CLIENT_ABSTRACT_PATTERNS)
  };
};

const providerLabel = (provider: 'openai' | 'anthropic') =>
  provider === 'openai' ? 'OpenAI' : 'Anthropic';

export default function RewritePage() {
  const [sourceText, setSourceText] = useState('');
  const [instruction, setInstruction] = useState('誇張や比喩を排除し、根拠が明確な表現に整えてください。');
  const [provider, setProvider] = useState<'openai' | 'anthropic'>('openai');
  const [model, setModel] = useState<string>('gpt-5');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<RewriteResponsePayload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const availableModels = useMemo(
    () => LLM_PRESETS.filter((option) => option.provider === provider),
    [provider]
  );

  const sourceDetection = useMemo(() => detectPhrases(sourceText), [sourceText]);
  const rewrittenDetection = useMemo(() => detectPhrases(result?.rewritten_text ?? ''), [result]);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);

    try {
      const payload: Record<string, unknown> = {
        text: sourceText,
        instruction,
        llm: {
          provider,
          model
        }
      };
      const response = await apiFetch<RewriteResponsePayload>('api/tools/rewrite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      setResult(response);
    } catch (err) {
      console.error(err);
      setError('リライトの実行に失敗しました。入力内容とモデル設定を確認してください。');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="部分リライト"
          description="文章をピンポイントでリライトし、過剰表現や抽象表現を自動検出します。"
        />
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-sm font-medium text-slate-700">プロバイダー</label>
                <select
                  value={provider}
                  onChange={(event) => {
                    const nextProvider = event.target.value as 'openai' | 'anthropic';
                    setProvider(nextProvider);
                    const first = LLM_PRESETS.find((option) => option.provider === nextProvider);
                    if (first) {
                      setModel(first.model);
                    }
                  }}
                  className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                >
                  {(['openai', 'anthropic'] as const).map((value) => (
                    <option key={value} value={value}>
                      {providerLabel(value)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">モデル</label>
                <select
                  value={model}
                  onChange={(event) => setModel(event.target.value)}
                  className="mt-2 w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                >
                  {availableModels.map((option) => (
                    <option key={option.id} value={option.model}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">リライト指示</label>
              <Input value={instruction} onChange={(event) => setInstruction(event.target.value)} />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">原文</label>
              <Textarea
                value={sourceText}
                onChange={(event) => setSourceText(event.target.value)}
                rows={8}
                placeholder="リライトしたい文章を貼り付けてください。"
              />
              {(sourceDetection.ng.length > 0 || sourceDetection.abstract.length > 0) && (
                <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                  <p className="font-semibold">検出された懸念表現</p>
                  {sourceDetection.ng.length > 0 ? (
                    <p>NG表現: {sourceDetection.ng.join(', ')}</p>
                  ) : null}
                  {sourceDetection.abstract.length > 0 ? (
                    <p>抽象表現: {sourceDetection.abstract.join(', ')}</p>
                  ) : null}
                </div>
              )}
            </div>

            <div className="flex items-center justify-end gap-3">
              {error ? <p className="text-sm text-red-600">{error}</p> : null}
              <Button type="submit" disabled={loading || !sourceText.trim()}>
                {loading ? 'リライト中…' : 'リライトを実行'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {result ? (
        <Card>
          <CardHeader title="リライト結果" description="検出済みのNG表現・抽象表現も確認できます。" />
          <CardContent className="space-y-4">
            <Textarea value={result.rewritten_text} readOnly rows={8} className="text-sm" />
            {rewrittenDetection.ng.length > 0 || rewrittenDetection.abstract.length > 0 ? (
              <div className="rounded-md border border-red-300 bg-red-50 p-3 text-xs text-red-900">
                <p className="font-semibold">出力内で検出された懸念表現</p>
                {rewrittenDetection.ng.length > 0 ? (
                  <p>NG表現: {rewrittenDetection.ng.join(', ')}</p>
                ) : null}
                {rewrittenDetection.abstract.length > 0 ? (
                  <p>抽象表現: {rewrittenDetection.abstract.join(', ')}</p>
                ) : null}
              </div>
            ) : (
              <p className="text-xs text-slate-500">懸念表現は検出されませんでした。</p>
            )}
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
