'use client';

import { FormEvent, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

type DraftIntent = 'information' | 'comparison' | 'transaction';

export default function BriefPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setLoading(true);
    setStatus(null);
    try {
      const payload = {
        primary_keyword: form.get('primary_keyword'),
        supporting_keywords: (form.get('supporting_keywords') as string)
          ?.split(',')
          .map((v) => v.trim())
          .filter(Boolean),
        intent: form.get('intent') || undefined,
        word_count_range: form.get('word_count_range') || undefined,
        prohibited_claims: (form.get('prohibited_claims') as string)
          ?.split('\n')
          .map((v) => v.trim())
          .filter(Boolean),
        style_guide_id: form.get('style_guide_id') || undefined,
        prompt_version: form.get('prompt_version') || undefined,
        existing_article_ids: (form.get('existing_article_ids') as string)
          ?.split(',')
          .map((v) => v.trim())
          .filter(Boolean)
      };
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://seo-drafter-api-yxk2eqrkvq-an.a.run.app';
      const response = await fetch(baseUrl + '/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const body = await response.json();
      setStatus(`ジョブ作成に成功しました: ${body.id}`);
      formElement.reset();
    } catch (error) {
      console.error(error);
      setStatus('ジョブ作成に失敗しました。バックエンド設定を確認してください。');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader title="記事作成依頼フォーム" description="生成に必要な情報を入力し、Cloud Workflows にジョブを登録します。" />
      <form onSubmit={onSubmit}>
        <CardContent className="space-y-6">
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="text-sm font-medium text-slate-700">主キーワード</label>
              <Input name="primary_keyword" placeholder="例: B2B マーケティング" required />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">検索意図タイプ</label>
              <select
                name="intent"
                className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
              >
                <option value="">自動推定</option>
                {(['information', 'comparison', 'transaction'] as DraftIntent[]).map((intent) => (
                  <option key={intent} value={intent}>
                    {intent}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="text-sm font-medium text-slate-700">サブキーワード</label>
              <Input name="supporting_keywords" placeholder="カンマ区切りで入力" />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">推奨文字数レンジ</label>
              <Input name="word_count_range" placeholder="例: 2000-2500" />
            </div>
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">既存関連記事ID</label>
            <Input name="existing_article_ids" placeholder="article-123, article-456" />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">禁止・注意事項</label>
            <Textarea name="prohibited_claims" rows={4} placeholder="1行に1つずつ入力" />
          </div>
          <div className="grid gap-4 md:grid-cols-2">
            <div>
              <label className="text-sm font-medium text-slate-700">スタイルガイド</label>
              <Input name="style_guide_id" placeholder="style-guide-default" />
            </div>
            <div>
              <label className="text-sm font-medium text-slate-700">プロンプトバージョン</label>
              <Input name="prompt_version" placeholder="v1" />
            </div>
          </div>
          {status ? <p className="text-sm text-slate-600">{status}</p> : null}
        </CardContent>
        <CardFooter>
          <Button type="submit" disabled={loading}>
            {loading ? '送信中...' : 'ジョブを作成'}
          </Button>
        </CardFooter>
      </form>
    </Card>
  );
}
