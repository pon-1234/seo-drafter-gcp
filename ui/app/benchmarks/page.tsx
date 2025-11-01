'use client';

import { FormEvent, useEffect, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { apiFetch } from '@/lib/api';
import { LLM_PRESETS } from '@/lib/llm-presets';

type ArticleType = 'information' | 'comparison' | 'ranking' | 'closing';

type BenchmarkVariant = {
  variant_id: string;
  llm: {
    provider: string;
    model: string;
    label?: string;
  };
  draft_id: string;
  processing_seconds: number;
  word_count: number;
  citation_count: number;
  quality: {
    duplication_score: number;
    excessive_claims: string[];
    style_violations: string[];
    requires_expert_review: boolean;
    citations_missing: string[];
    citation_count: number;
    numeric_facts: number;
    banned_phrase_hits: string[];
    abstract_phrase_hits: string[];
    rubric_summary?: string;
  };
  metadata: Record<string, unknown>;
  excerpt: string;
};

type BenchmarkRun = {
  id: string;
  primary_keyword: string;
  article_type: ArticleType;
  created_at: string;
  variants: BenchmarkVariant[];
};

type QualityKpiSummary = {
  sample_size: number;
  avg_duplication: number;
  avg_citation_count: number;
  avg_numeric_facts: number;
  ng_phrase_rate: number;
  abstract_phrase_rate: number;
};

const providerLabel = (provider: string) => (provider === 'anthropic' ? 'Anthropic' : 'OpenAI');

const parseList = (value: string) =>
  value
    .split(/[\n,、，]+/)
    .map((item) => item.trim())
    .filter(Boolean);

export default function BenchmarkPage() {
  const [primaryKeyword, setPrimaryKeyword] = useState('');
  const [supportingKeywords, setSupportingKeywords] = useState('');
  const [articleType, setArticleType] = useState<ArticleType>('information');
  const [baseProvider, setBaseProvider] = useState<'openai' | 'anthropic'>('openai');
  const [baseModel, setBaseModel] = useState('gpt-4o');
  const [selectedVariants, setSelectedVariants] = useState<string[]>(['openai:gpt-4o', 'anthropic:claude-3-5-sonnet-20240620']);
  const [referenceUrls, setReferenceUrls] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [result, setResult] = useState<BenchmarkRun | null>(null);
  const [qualitySummary, setQualitySummary] = useState<QualityKpiSummary | null>(null);
  const [qualityError, setQualityError] = useState<string | null>(null);

  const availableBaseModels = useMemo(
    () => LLM_PRESETS.filter((option) => option.provider === baseProvider),
    [baseProvider]
  );

  useEffect(() => {
    const controller = new AbortController();
    apiFetch<QualityKpiSummary>('api/analytics/quality-kpis', { signal: controller.signal })
      .then(setQualitySummary)
      .catch((error) => {
        if ((error as Error).name !== 'AbortError') {
          setQualityError('品質KPIの取得に失敗しました');
        }
      });
    return () => controller.abort();
  }, []);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!primaryKeyword.trim()) {
      setStatus('主キーワードを入力してください。');
      return;
    }
    if (selectedVariants.length === 0) {
      setStatus('ベンチマーク対象モデルを1つ以上選択してください。');
      return;
    }

    setLoading(true);
    setStatus(null);
    setResult(null);

    try {
      const benchmarkPlan = selectedVariants
        .map((id) => {
          const preset = LLM_PRESETS.find((item) => item.id === id);
          if (!preset) return null;
          return {
            provider: preset.provider,
            model: preset.model,
            label: preset.label
          };
        })
        .filter(Boolean);

      const payload: Record<string, unknown> = {
        primary_keyword: primaryKeyword.trim(),
        supporting_keywords: parseList(supportingKeywords),
        article_type: articleType,
        benchmark_plan: benchmarkPlan,
        llm: {
          provider: baseProvider,
          model: baseModel
        },
        reference_urls: parseList(referenceUrls)
      };

      const response = await apiFetch<BenchmarkRun>('api/benchmarks/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      setResult(response);
      setStatus(`ベンチマークID: ${response.id}`);
    } catch (err) {
      console.error(err);
      setStatus('ベンチマークの実行に失敗しました。入力内容を確認してください。');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader
          title="ベンチマーク比較"
          description="複数モデルで同一条件のドラフトを生成し、品質指標を並べて確認します。"
        />
        <CardContent>
          <form className="space-y-4" onSubmit={onSubmit}>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-sm font-medium text-slate-700">主キーワード</label>
                <Input
                  value={primaryKeyword}
                  onChange={(event) => setPrimaryKeyword(event.target.value)}
                  placeholder="例: サイトコントローラー おすすめ"
                  required
                />
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">記事タイプ</label>
                <select
                  value={articleType}
                  onChange={(event) => setArticleType(event.target.value as ArticleType)}
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                >
                  {(['information', 'comparison', 'ranking', 'closing'] as ArticleType[]).map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">補助キーワード（カンマ / 改行区切り）</label>
              <Textarea
                rows={2}
                value={supportingKeywords}
                onChange={(event) => setSupportingKeywords(event.target.value)}
              />
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <label className="text-sm font-medium text-slate-700">ベースプロバイダー</label>
                <select
                  value={baseProvider}
                  onChange={(event) => {
                    const nextProvider = event.target.value as 'openai' | 'anthropic';
                    setBaseProvider(nextProvider);
                    const first = LLM_PRESETS.find((option) => option.provider === nextProvider);
                    if (first) {
                      setBaseModel(first.model);
                    }
                  }}
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                >
                  {(['openai', 'anthropic'] as const).map((value) => (
                    <option key={value} value={value}>
                      {providerLabel(value)}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="text-sm font-medium text-slate-700">ベースモデル</label>
                <select
                  value={baseModel}
                  onChange={(event) => setBaseModel(event.target.value)}
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                >
                  {availableBaseModels.map((option) => (
                    <option key={option.id} value={option.model}>
                      {option.label}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">ベンチマーク対象モデル</label>
              <div className="grid gap-2 md:grid-cols-2">
                {LLM_PRESETS.map((option) => (
                  <label key={option.id} className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      className="h-4 w-4"
                      checked={selectedVariants.includes(option.id)}
                      onChange={(event) => {
                        setSelectedVariants((prev) =>
                          event.target.checked
                            ? [...prev, option.id]
                            : prev.filter((id) => id !== option.id)
                        );
                      }}
                    />
                    <span>{option.label}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-slate-500">
                選択したモデルそれぞれで同一プロンプトが実行され、品質指標が比較できます。
              </p>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-slate-700">参考URL（任意）</label>
              <Textarea
                rows={2}
                value={referenceUrls}
                onChange={(event) => setReferenceUrls(event.target.value)}
                placeholder={'参考にする一次情報のURLを入力 \n例:\nhttps://example.com/report'}
              />
            </div>

            <div className="flex items-center justify-end gap-3">
              {status ? <p className="text-sm text-slate-600">{status}</p> : null}
              <Button type="submit" disabled={loading}>
                {loading ? '実行中…' : 'ベンチマークを実行'}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {result ? (
        <Card>
          <CardHeader title="比較結果" description="各モデルの生成結果と品質指標" />
          <CardContent>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">モデル</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">ワード数</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">出典数</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">数値根拠</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">スタイル警告</th>
                    <th className="px-4 py-2 text-left font-semibold text-slate-700">処理時間</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {result.variants.map((variant) => (
                    <tr key={variant.variant_id} className="hover:bg-slate-50">
                      <td className="px-4 py-3">
                        <div className="font-medium text-slate-900">
                          {variant.llm.label || variant.llm.model}
                        </div>
                        <div className="text-xs text-slate-500">
                          {providerLabel(variant.llm.provider)} / {variant.llm.model}
                        </div>
                      </td>
                      <td className="px-4 py-3">{variant.word_count}</td>
                      <td className="px-4 py-3">{variant.quality.citation_count}</td>
                      <td className="px-4 py-3">{variant.quality.numeric_facts}</td>
                      <td className="px-4 py-3">
                        {variant.quality.style_violations.length > 0 ? (
                          <ul className="space-y-1 text-xs text-red-700">
                            {variant.quality.style_violations.map((flag) => (
                              <li key={flag}>{flag}</li>
                            ))}
                          </ul>
                        ) : (
                          <span className="text-xs text-slate-500">なし</span>
                        )}
                      </td>
                      <td className="px-4 py-3">{variant.processing_seconds.toFixed(2)} 秒</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader title="直近の品質KPI" description="保存されたドラフトから算出した平均値" />
        <CardContent>
          {qualityError ? (
            <p className="text-sm text-red-600">{qualityError}</p>
          ) : qualitySummary ? (
            <dl className="grid gap-4 md:grid-cols-3 text-sm">
              <div>
                <dt className="font-medium text-slate-700">サンプル数</dt>
                <dd className="text-slate-900">{qualitySummary.sample_size}</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-700">平均重複率</dt>
                <dd className="text-slate-900">{(qualitySummary.avg_duplication * 100).toFixed(1)}%</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-700">平均出典数</dt>
                <dd className="text-slate-900">{qualitySummary.avg_citation_count.toFixed(2)} 件</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-700">平均数値根拠件数</dt>
                <dd className="text-slate-900">{qualitySummary.avg_numeric_facts.toFixed(2)} 件</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-700">NG表現検出率</dt>
                <dd className="text-slate-900">{(qualitySummary.ng_phrase_rate * 100).toFixed(1)}%</dd>
              </div>
              <div>
                <dt className="font-medium text-slate-700">抽象表現検出率</dt>
                <dd className="text-slate-900">{(qualitySummary.abstract_phrase_rate * 100).toFixed(1)}%</dd>
              </div>
            </dl>
          ) : (
            <p className="text-sm text-slate-500">データを読み込み中です…</p>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
