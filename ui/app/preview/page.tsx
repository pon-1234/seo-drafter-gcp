'use client';

import { ChangeEvent, FormEvent, useState, useEffect, Suspense, useRef } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { apiFetch } from '@/lib/api';

interface InternalLink {
  url: string;
  title: string;
  anchor: string;
  score: number;
  snippet?: string;
}

interface StyleRewriteMetrics {
  elapsed_seconds: number;
  paragraph_count: number;
  seconds_per_paragraph: number;
  total_paragraph_count?: number;
  sample_only?: boolean;
}

interface DraftBundle {
  draft_id: string;
  gcs_paths: Record<string, string>;
  signed_urls?: Record<string, string>;
  quality: {
    duplication_score: number;
    excessive_claims: string[];
    style_violations: string[];
    requires_expert_review: boolean;
    citations_missing: string[];
    rubric_scores?: Record<string, string>;
    rubric_summary?: string;
    citation_count?: number;
    numeric_facts?: number;
    banned_phrase_hits?: string[];
    abstract_phrase_hits?: string[];
  };
  metadata: Record<string, string>;
  meta?: Record<string, unknown>;
  internal_links?: InternalLink[];
  draft_content?: string;
  style_rewrite_metrics?: StyleRewriteMetrics | null;
  style_rewritten?: boolean;
  validation_warnings?: string[];
  editor_checklist?: string | null;
}

interface RewriteResponsePayload {
  rewritten_text: string;
  detected_ng_phrases: string[];
  detected_abstract_phrases: string[];
}

function PreviewPageContent() {
  const searchParams = useSearchParams();
  const [draftId, setDraftId] = useState('');
  const [bundle, setBundle] = useState<DraftBundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [draftText, setDraftText] = useState('');
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const [selection, setSelection] = useState({ start: 0, end: 0, text: '' });
  const [instruction, setInstruction] = useState('誇張表現を抑え、具体的な根拠を盛り込んで書き換えてください。');
  const [rewriteResult, setRewriteResult] = useState<string | null>(null);
  const [rewriteDetections, setRewriteDetections] = useState<{ ng: string[]; abstract: string[] }>({ ng: [], abstract: [] });
  const [rewriteLoading, setRewriteLoading] = useState(false);
  const [rewriteError, setRewriteError] = useState<string | null>(null);
  const metaString = (key: string): string | undefined => {
    const value = bundle?.meta?.[key];
    return typeof value === 'string' ? value : undefined;
  };
  const resolvedTitle =
    metaString('final_title') ||
    bundle?.metadata?.['final_title'] ||
    metaString('provisional_title') ||
    bundle?.metadata?.['provisional_title'] ||
    undefined;
  const provisionalTitleValue = metaString('provisional_title') || bundle?.metadata?.['provisional_title'];
  const showProvisionalTitle =
    Boolean(provisionalTitleValue && resolvedTitle && provisionalTitleValue !== resolvedTitle);

  // Load draft from URL query parameter on mount
  useEffect(() => {
    const draftIdFromUrl = searchParams.get('draft_id');
    if (draftIdFromUrl) {
      setDraftId(draftIdFromUrl);
      fetchDraft(draftIdFromUrl);
    }
  }, [searchParams]);

  const fetchDraft = async (id: string) => {
    setError(null);
    setBundle(null);
    setDraftText('');
    setSelection({ start: 0, end: 0, text: '' });
    setRewriteResult(null);
    setRewriteError(null);
    setRewriteDetections({ ng: [], abstract: [] });
    try {
      const json = await apiFetch<DraftBundle>(`api/drafts/${id}`);
      setBundle(json);
      setDraftText(json.draft_content ?? '');
    } catch (err) {
      console.error(err);
      setError('ドラフトの取得に失敗しました。');
    }
  };

  const resetRewriteOutputs = () => {
    setRewriteResult(null);
    setRewriteDetections({ ng: [], abstract: [] });
    setRewriteError(null);
  };

  const updateSelectionFromTextarea = () => {
    const textarea = textareaRef.current;
    if (!textarea) {
      return;
    }
    const start = textarea.selectionStart ?? 0;
    const end = textarea.selectionEnd ?? 0;
    const selectedText = start !== end ? textarea.value.slice(start, end) : '';
    setSelection({ start, end, text: selectedText });
    if (rewriteResult && selectedText !== selection.text) {
      resetRewriteOutputs();
    }
  };

  const handleDraftTextChange = (event: ChangeEvent<HTMLTextAreaElement>) => {
    setDraftText(event.target.value);
    resetRewriteOutputs();
    setSelection({ start: 0, end: 0, text: '' });
  };

  const rewriteSelectedText = async () => {
    const trimmed = selection.text.trim();
    if (!trimmed) {
      setRewriteError('リライトする文章を選択してください。');
      return;
    }

    setRewriteLoading(true);
    setRewriteError(null);

    try {
      const provider = (bundle?.metadata?.['llm_provider'] as string) || 'openai';
      const model = bundle?.metadata?.['llm_model'] as string | undefined;
      const payload: Record<string, unknown> = {
        text: selection.text,
        instruction: instruction.trim() || '誇張表現を抑えて具体的に書き換えてください。',
        llm: {
          provider,
          model,
        },
      };

      const response = await apiFetch<RewriteResponsePayload>('api/tools/rewrite', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      setRewriteResult(response.rewritten_text);
      setRewriteDetections({
        ng: response.detected_ng_phrases ?? [],
        abstract: response.detected_abstract_phrases ?? [],
      });
    } catch (err) {
      console.error(err);
      setRewriteError('リライトに失敗しました。時間をおいて再試行してください。');
    } finally {
      setRewriteLoading(false);
    }
  };

  const applyRewrite = () => {
    if (!rewriteResult) {
      return;
    }
    const before = draftText.slice(0, selection.start);
    const after = draftText.slice(selection.end);
    const nextText = `${before}${rewriteResult}${after}`;
    const newStart = before.length;
    const newEnd = newStart + rewriteResult.length;

    setDraftText(nextText);
    resetRewriteOutputs();
    setSelection({ start: newStart, end: newEnd, text: rewriteResult });

    requestAnimationFrame(() => {
      const textarea = textareaRef.current;
      if (textarea) {
        textarea.focus();
        textarea.setSelectionRange(newStart, newEnd);
      }
    });
  };

  const cancelRewrite = () => {
    resetRewriteOutputs();
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    await fetchDraft(draftId);
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="生成プレビュー" description="Firestore / GCS に保存されたドラフトをプレビューします。" />
        <CardContent>
          <form className="flex gap-3" onSubmit={onSubmit}>
            <Input value={draftId} onChange={(event) => setDraftId(event.target.value)} placeholder="draft-id" />
            <Button type="submit">読み込む</Button>
          </form>
          {error ? <p className="mt-4 text-sm text-red-500">{error}</p> : null}
        </CardContent>
      </Card>
      {bundle ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card className="lg:col-span-2">
            <CardHeader title="生成された本文" description="Markdown形式のドラフト記事。選択範囲を指定して部分リライトできます。" />
            <CardContent className="space-y-4">
              <Textarea
                ref={textareaRef}
                value={draftText}
                onChange={handleDraftTextChange}
                onSelect={updateSelectionFromTextarea}
                onKeyUp={updateSelectionFromTextarea}
                onMouseUp={updateSelectionFromTextarea}
                rows={24}
                className="font-mono text-xs"
                placeholder="ドラフト本文がここに表示されます。"
              />
              <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-slate-600">
                    選択文字数: {Math.max(0, selection.end - selection.start)} / 全体 {draftText.length}
                  </p>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      onClick={rewriteSelectedText}
                      disabled={rewriteLoading || !selection.text.trim()}
                    >
                      {rewriteLoading ? 'リライト中…' : '選択範囲をリライト'}
                    </Button>
                    <Button
                      type="button"
                      variant="secondary"
                      onClick={() => {
                        if (textareaRef.current) {
                          textareaRef.current.focus();
                          textareaRef.current.select();
                          updateSelectionFromTextarea();
                        }
                      }}
                    >
                      全文を選択
                    </Button>
                    {rewriteResult ? (
                      <>
                        <Button type="button" variant="secondary" onClick={applyRewrite}>
                          リライト結果を適用
                        </Button>
                        <Button type="button" variant="secondary" onClick={cancelRewrite}>
                          結果をクリア
                        </Button>
                      </>
                    ) : null}
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-medium text-slate-700">リライト指示</label>
                  <Textarea
                    rows={2}
                    value={instruction}
                    onChange={(event) => setInstruction(event.target.value)}
                    className="text-xs"
                  />
                </div>
                {rewriteError ? <p className="text-xs text-red-600">{rewriteError}</p> : null}
              </div>
              {rewriteResult ? (
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold text-slate-800">元のテキスト</h4>
                    <pre className="whitespace-pre-wrap rounded-md border border-slate-200 bg-white p-3 text-xs text-slate-700">
                      {selection.text}
                    </pre>
                  </div>
                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold text-slate-800">リライト候補</h4>
                    <pre className="whitespace-pre-wrap rounded-md border border-emerald-200 bg-emerald-50 p-3 text-xs text-slate-700">
                      {rewriteResult}
                    </pre>
                    {(rewriteDetections.ng.length > 0 || rewriteDetections.abstract.length > 0) && (
                      <div className="rounded-md border border-amber-300 bg-amber-50 p-3 text-xs text-amber-900">
                        <p className="font-semibold">検出された懸念表現</p>
                        {rewriteDetections.ng.length > 0 ? (
                          <p>NG表現: {rewriteDetections.ng.join(', ')}</p>
                        ) : null}
                        {rewriteDetections.abstract.length > 0 ? (
                          <p>抽象表現: {rewriteDetections.abstract.join(', ')}</p>
                        ) : null}
                      </div>
                    )}
                  </div>
                </div>
              ) : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader title="生成情報" description="この記事がどのようなパラメータで生成されたか" />
            <CardContent>
              <div className="space-y-4">
                {/* 基本情報 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-slate-800 border-b border-slate-200 pb-1">基本情報</h4>
                  <div className="grid gap-2 text-sm">
                    <div className="flex items-start gap-3">
                      <span className="w-24 flex-shrink-0 text-slate-600">タイトル:</span>
                      <div className="flex flex-col gap-0.5">
                        <span className="font-semibold text-slate-900">{resolvedTitle ?? 'Untitled'}</span>
                        {showProvisionalTitle && provisionalTitleValue ? (
                          <span className="text-xs text-slate-500">仮タイトル: {provisionalTitleValue}</span>
                        ) : null}
                      </div>
                    </div>
                    {bundle.metadata.job_id && (
                      <div className="flex items-start gap-3">
                        <span className="w-24 flex-shrink-0 text-slate-600">Job ID:</span>
                        <span className="font-mono text-xs text-slate-900">{bundle.metadata.job_id}</span>
                      </div>
                    )}
                    {bundle.metadata.created_at && (
                      <div className="flex items-start gap-3">
                        <span className="w-24 flex-shrink-0 text-slate-600">生成日時:</span>
                        <span className="text-slate-900">{new Date(bundle.metadata.created_at).toLocaleString('ja-JP')}</span>
                      </div>
                    )}
                    {bundle.metadata.primary_keyword && (
                      <div className="flex items-start gap-3">
                        <span className="w-24 flex-shrink-0 text-slate-600">主キーワード:</span>
                        <span className="font-medium text-slate-900">{bundle.metadata.primary_keyword}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* コンテンツ設定 */}
                <div className="space-y-2">
                  <h4 className="text-sm font-semibold text-slate-800 border-b border-slate-200 pb-1">コンテンツ設定</h4>
                  <div className="grid gap-2 text-sm">
                    {bundle.metadata.expertise_level && (
                      <div className="flex items-start gap-3">
                        <span className="w-24 flex-shrink-0 text-slate-600">専門性:</span>
                        <span className="inline-flex items-center rounded-full bg-blue-100 px-2.5 py-0.5 text-xs font-medium text-blue-800">
                          {bundle.metadata.expertise_level === 'beginner' && '初心者向け'}
                          {bundle.metadata.expertise_level === 'intermediate' && '中級者向け'}
                          {bundle.metadata.expertise_level === 'expert' && '専門家向け'}
                        </span>
                      </div>
                    )}
                    {bundle.metadata.tone && (
                      <div className="flex items-start gap-3">
                        <span className="w-24 flex-shrink-0 text-slate-600">トーン:</span>
                        <span className="inline-flex items-center rounded-full bg-purple-100 px-2.5 py-0.5 text-xs font-medium text-purple-800">
                          {bundle.metadata.tone === 'casual' && '親しみやすい'}
                          {bundle.metadata.tone === 'formal' && 'フォーマル'}
                        </span>
                      </div>
                    )}
                    {bundle.metadata.article_type && (
                      <div className="flex items-start gap-3">
                        <span className="w-24 flex-shrink-0 text-slate-600">記事タイプ:</span>
                        <span className="text-slate-900">{bundle.metadata.article_type}</span>
                      </div>
                    )}
                    {bundle.metadata.word_count_range && (
                      <div className="flex items-start gap-3">
                        <span className="w-24 flex-shrink-0 text-slate-600">文字数:</span>
                        <span className="text-slate-900">{bundle.metadata.word_count_range}</span>
                      </div>
                    )}
                    {bundle.metadata.output_format && (
                      <div className="flex items-start gap-3">
                        <span className="w-24 flex-shrink-0 text-slate-600">出力形式:</span>
                        <span className="text-slate-900">{bundle.metadata.output_format}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* プロンプト・品質設定 */}
                {(bundle.metadata.prompt_version || bundle.metadata.intended_cta || bundle.metadata.quality_rubric) && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold text-slate-800 border-b border-slate-200 pb-1">プロンプト・品質設定</h4>
                    <div className="grid gap-2 text-sm">
                      {bundle.metadata.prompt_version && (
                        <div className="flex items-start gap-3">
                          <span className="w-24 flex-shrink-0 text-slate-600">バージョン:</span>
                          <span className="font-mono text-xs text-slate-900">{bundle.metadata.prompt_version}</span>
                        </div>
                      )}
                      {bundle.metadata.intended_cta && (
                        <div className="flex items-start gap-3">
                          <span className="w-24 flex-shrink-0 text-slate-600">意図CTA:</span>
                          <span className="text-slate-900">{bundle.metadata.intended_cta}</span>
                        </div>
                      )}
                      {bundle.metadata.quality_rubric && (
                        <div className="flex items-start gap-3">
                          <span className="w-24 flex-shrink-0 text-slate-600">品質Rubric:</span>
                          <span className="text-slate-900">{bundle.metadata.quality_rubric}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {/* LLM設定 */}
                {(bundle.metadata.llm_provider || bundle.metadata.llm_model) && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold text-slate-800 border-b border-slate-200 pb-1">LLM設定</h4>
                    <div className="grid gap-2 text-sm">
                      {bundle.metadata.llm_provider && (
                        <div className="flex items-start gap-3">
                          <span className="w-24 flex-shrink-0 text-slate-600">プロバイダー:</span>
                          <span className="inline-flex items-center rounded-full bg-green-100 px-2.5 py-0.5 text-xs font-medium text-green-800">
                            {bundle.metadata.llm_provider}
                          </span>
                        </div>
                      )}
                      {bundle.metadata.llm_model && (
                        <div className="flex items-start gap-3">
                          <span className="w-24 flex-shrink-0 text-slate-600">モデル:</span>
                          <span className="font-mono text-xs text-slate-900">{bundle.metadata.llm_model}</span>
                        </div>
                      )}
                    </div>
                  </div>
                )}

                {(bundle.style_rewrite_metrics || (bundle.validation_warnings && bundle.validation_warnings.length > 0)) && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold text-slate-800 border-b border-slate-200 pb-1">スタイル調整</h4>
                    <div className="grid gap-2 text-sm">
                      <div className="flex items-start gap-3">
                        <span className="w-24 flex-shrink-0 text-slate-600">適用状況:</span>
                        <span className="text-slate-900">
                          {bundle.style_rewritten ? 'LLMリライト適用済み' : '未適用（原文のまま）'}
                        </span>
                      </div>
                      {bundle.style_rewrite_metrics ? (
                        <>
                          <div className="flex items-start gap-3">
                            <span className="w-24 flex-shrink-0 text-slate-600">処理時間:</span>
                            <span className="text-slate-900">
                              {bundle.style_rewrite_metrics.elapsed_seconds.toFixed(2)} 秒 /{' '}
                              {bundle.style_rewrite_metrics.paragraph_count} 段落
                            </span>
                          </div>
                          <div className="flex items-start gap-3">
                            <span className="w-24 flex-shrink-0 text-slate-600">平均:</span>
                            <span className="text-slate-900">
                              {bundle.style_rewrite_metrics.seconds_per_paragraph.toFixed(2)} 秒 / 段落
                              {bundle.style_rewrite_metrics.sample_only ? '（サンプルモード）' : ''}
                            </span>
                          </div>
                        </>
                      ) : null}
                    </div>
                    {bundle.validation_warnings && bundle.validation_warnings.length > 0 ? (
                      <div className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900">
                        <p className="font-semibold">検出された注意事項</p>
                        <ul className="mt-2 list-disc pl-5">
                          {bundle.validation_warnings.map((warning, index) => (
                            <li key={`${warning}-${index}`}>{warning}</li>
                          ))}
                        </ul>
                        <p className="mt-2 text-[11px] text-amber-800">最終チェック時に目視でご確認ください。</p>
                      </div>
                    ) : null}
                  </div>
                )}

                {bundle.editor_checklist && (
                  <div className="space-y-2">
                    <h4 className="text-sm font-semibold text-slate-800 border-b border-slate-200 pb-1">
                      ライター向けチェックリスト
                    </h4>
                    <pre className="whitespace-pre-wrap rounded-md border border-slate-200 bg-slate-50 p-3 text-xs text-slate-800">
                      {bundle.editor_checklist}
                    </pre>
                  </div>
                )}

                {/* その他のメタデータ（デバッグ用） */}
                <details className="mt-4">
                  <summary className="cursor-pointer text-xs text-slate-500 hover:text-slate-700">
                    すべてのメタデータを表示
                  </summary>
                  <pre className="mt-2 whitespace-pre-wrap rounded-md bg-slate-100 p-3 text-xs text-slate-700">
                    {JSON.stringify(bundle.metadata, null, 2)}
                  </pre>
                </details>
              </div>
            </CardContent>
          </Card>
          <Card>
            <CardHeader title="GCSパス" />
            <CardContent>
              <ul className="space-y-2 text-sm text-slate-700">
                {Object.entries(bundle.gcs_paths).map(([key, value]) => (
                  <li key={key} className="flex items-center justify-between gap-4">
                    <span className="font-medium text-slate-600">{key}</span>
                    <span className="truncate">{value}</span>
                  </li>
                ))}
              </ul>
              {bundle.signed_urls ? (
                <div className="mt-4 space-y-2 text-sm">
                  <p className="font-semibold text-slate-700">署名付きURL</p>
                  {Object.entries(bundle.signed_urls).map(([key, value]) => (
                    <a key={key} href={value} className="block truncate text-primary" target="_blank" rel="noreferrer">
                      {key}
                    </a>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>
          <Card>
            <CardHeader title="品質指標" />
            <CardContent>
              <ul className="space-y-2 text-sm text-slate-700">
                <li>重複率: {(bundle.quality.duplication_score * 100).toFixed(1)}%</li>
                <li>要出典: {bundle.quality.citations_missing.length} 件</li>
                <li>専門家レビュー: {bundle.quality.requires_expert_review ? '必須' : '任意'}</li>
                <li>出典数: {bundle.quality.citation_count ?? '-'} 件</li>
                <li>数値根拠: {bundle.quality.numeric_facts ?? '-'} 件</li>
                <li>過剰表現検出: {bundle.quality.banned_phrase_hits?.length ?? 0} 件</li>
                <li>抽象表現検出: {bundle.quality.abstract_phrase_hits?.length ?? 0} 件</li>
                {bundle.quality.rubric_summary ? (
                  <li>Rubricサマリー: {bundle.quality.rubric_summary}</li>
                ) : null}
              </ul>
              {bundle.quality.style_violations.length > 0 ? (
                <div className="mt-3 space-y-1 text-xs text-red-700">
                  <p className="font-semibold">スタイル警告</p>
                  <ul className="list-disc pl-5">
                    {bundle.quality.style_violations.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {bundle.quality.rubric_scores ? (
                <div className="mt-4 space-y-1 text-sm text-slate-700">
                  <p className="font-semibold text-slate-800">Rubric詳細（5観点）</p>
                  {Object.entries(bundle.quality.rubric_scores).map(([key, value]) => (
                    <div key={key} className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2">
                      <span className="text-slate-600">{key}</span>
                      <span className="font-medium text-slate-900">{value}</span>
                    </div>
                  ))}
                </div>
              ) : null}
              {bundle.metadata['serp_gap_topics'] ? (
                <p className="mt-3 text-xs text-slate-500">
                  差別化トピック: {bundle.metadata['serp_gap_topics']}
                </p>
              ) : null}
            </CardContent>
          </Card>
          {bundle.internal_links && bundle.internal_links.length > 0 ? (
            <Card className="lg:col-span-2">
              <CardHeader title="内部リンク候補" description="BigQuery Vector Search による関連記事の提案" />
              <CardContent>
                <div className="space-y-4">
                  {bundle.internal_links.map((link, index) => (
                    <div key={index} className="rounded-lg border border-slate-200 p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1">
                          <h3 className="font-semibold text-slate-900">{link.title}</h3>
                          <a
                            href={link.url}
                            className="mt-1 block text-sm text-primary hover:underline"
                            target="_blank"
                            rel="noreferrer"
                          >
                            {link.url}
                          </a>
                          {link.snippet ? (
                            <p className="mt-2 text-sm text-slate-600">{link.snippet}</p>
                          ) : null}
                          <p className="mt-2 text-xs text-slate-500">
                            推奨アンカーテキスト: <span className="font-medium">{link.anchor}</span>
                          </p>
                        </div>
                        <div className="flex-shrink-0">
                          <span className="inline-flex items-center rounded-full bg-primary/10 px-3 py-1 text-sm font-medium text-primary">
                            {(link.score * 100).toFixed(0)}%
                          </span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}

export default function PreviewPage() {
  return (
    <Suspense fallback={<div>Loading...</div>}>
      <PreviewPageContent />
    </Suspense>
  );
}
