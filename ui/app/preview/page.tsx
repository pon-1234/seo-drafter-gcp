'use client';

import { FormEvent, useState } from 'react';
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
  };
  metadata: Record<string, string>;
  internal_links?: InternalLink[];
}

export default function PreviewPage() {
  const [draftId, setDraftId] = useState('');
  const [bundle, setBundle] = useState<DraftBundle | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setBundle(null);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';
      const response = await fetch(baseUrl + `/api/drafts/${draftId}`);
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
              </ul>
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
