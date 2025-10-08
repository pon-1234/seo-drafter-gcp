'use client';

import { FormEvent, useState, useEffect, Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

interface InternalLink {
  url: string;
  title: string;
  anchor: string;
  score: number;
  snippet?: string;
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
  };
  metadata: Record<string, string>;
  internal_links?: InternalLink[];
  draft_content?: string;
}

function PreviewPageContent() {
  const searchParams = useSearchParams();
  const [draftId, setDraftId] = useState('');
  const [bundle, setBundle] = useState<DraftBundle | null>(null);
  const [error, setError] = useState<string | null>(null);

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
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://seo-drafter-api-yxk2eqrkvq-an.a.run.app';
      const response = await fetch(baseUrl + `/api/drafts/${id}`);
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const json = await response.json();
      setBundle(json);
    } catch (err) {
      console.error(err);
      setError('ドラフトの取得に失敗しました。');
    }
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
          {bundle.draft_content ? (
            <Card className="lg:col-span-2">
              <CardHeader title="生成された本文" description="Markdown形式のドラフト記事" />
              <CardContent>
                <div className="prose prose-slate max-w-none">
                  <pre className="whitespace-pre-wrap text-sm text-slate-700">{bundle.draft_content}</pre>
                </div>
              </CardContent>
            </Card>
          ) : null}
          <Card>
            <CardHeader title="メタデータ" />
            <CardContent>
              <pre className="whitespace-pre-wrap text-sm text-slate-700">{JSON.stringify(bundle.metadata, null, 2)}</pre>
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
                {bundle.quality.rubric_summary ? (
                  <li>Rubricサマリー: {bundle.quality.rubric_summary}</li>
                ) : null}
              </ul>
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
