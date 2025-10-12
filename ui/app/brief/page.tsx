'use client';

import { FormEvent, useMemo, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

type DraftIntent = 'information' | 'comparison' | 'transaction';
type ArticleType = 'information' | 'comparison' | 'ranking' | 'closing';
type OutputFormat = 'docs' | 'html';
type HeadingMode = 'auto' | 'manual';

const Label = ({ text, required = false }: { text: string; required?: boolean }) => (
  <label className="text-sm font-medium text-slate-700">
    {text}
    <span className="ml-2 inline-flex items-center rounded-full border border-slate-200 px-2 py-0.5 text-[10px] font-semibold tracking-wide text-slate-500">
      {required ? '必須' : '任意'}
    </span>
  </label>
);

export default function BriefPage() {
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [headingMode, setHeadingMode] = useState<HeadingMode>('auto');

  const articleTypes: ArticleType[] = useMemo(() => ['information', 'comparison', 'ranking', 'closing'], []);
  const outputFormats: OutputFormat[] = useMemo(() => ['docs', 'html'], []);
  const rubrics = useMemo(() => ['standard', 'eeat-focused', 'originality-plus'], []);

  const parseList = (value: FormDataEntryValue | null, mode: 'flex' | 'newline' = 'flex'): string[] => {
    if (!value) return [];
    const text = String(value);
    const pattern = mode === 'newline' ? /[\r\n]+/ : /[\r\n,、，]+/;
    return text
      .split(pattern)
      .map((item) => item.trim())
      .filter(Boolean);
  };

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const formElement = event.currentTarget;
    const form = new FormData(formElement);
    setLoading(true);
    setStatus(null);
    try {
      const personaJobRole = (form.get('persona_job_role') as string)?.trim();
      const personaBrief = personaJobRole
        ? {
            job_role: personaJobRole,
            experience_years: ((form.get('persona_experience_years') as string) || '').trim() || undefined,
            needs: parseList(form.get('persona_needs'), 'newline'),
            prohibited_expressions: parseList(form.get('persona_prohibited_expressions'), 'newline'),
          }
        : undefined;

      const headingModeValue = (form.get('heading_mode') as HeadingMode) || 'auto';
      const payload = {
        primary_keyword: form.get('primary_keyword'),
        supporting_keywords: parseList(form.get('supporting_keywords')),
        intent: (form.get('intent') as DraftIntent) || undefined,
        article_type: (form.get('article_type') as ArticleType) || 'information',
        word_count_range: ((form.get('word_count_range') as string) || '').trim() || undefined,
        output_format: (form.get('output_format') as OutputFormat) || 'html',
        quality_rubric: ((form.get('quality_rubric') as string) || '').trim() || undefined,
        prohibited_claims: parseList(form.get('forbidden_words'), 'newline'),
        style_guide_id: ((form.get('style_guide_id') as string) || '').trim() || undefined,
        prompt_version: ((form.get('prompt_version') as string) || '').trim() || undefined,
        existing_article_ids: parseList(form.get('existing_article_ids')),
        persona_brief: personaBrief,
        intended_cta: ((form.get('intended_cta') as string) || '').trim() || undefined,
        notation_guidelines: ((form.get('notation_guidelines') as string) || '').trim() || undefined,
        heading_directive: {
          mode: headingModeValue,
          headings: headingModeValue === 'manual' ? parseList(form.get('heading_overrides'), 'newline') : [],
        },
        reference_urls: parseList(form.get('reference_urls'), 'newline'),
      };

      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://seo-drafter-api-yxk2eqrkvq-an.a.run.app';
      const response = await fetch(baseUrl + '/api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const body = await response.json();
      setStatus(`ジョブ作成に成功しました: ${body.id}`);
      formElement.reset();
      setHeadingMode('auto');
    } catch (error) {
      console.error(error);
      setStatus('ジョブ作成に失敗しました。入力内容とバックエンド設定を確認してください。');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Card>
      <CardHeader
        title="記事作成依頼フォーム"
        description="ラベルに「必須」とある項目はすべて入力してください。送信するとプロンプトとペルソナ設定に値が転記され、Cloud Workflows で生成ジョブが開始されます。"
      />
      <form onSubmit={onSubmit}>
        <CardContent className="space-y-8">
          <section className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-900">基本情報</h3>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="主キーワード" required />
                <Input name="primary_keyword" placeholder="例: デジタルマーケティング とは" required />
              </div>
              <div>
                <Label text="記事タイプ" required />
                <select
                  name="article_type"
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                  required
                >
                  {articleTypes.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <Label text="検索意図タイプ" />
                <select
                  name="intent"
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                >
                  <option value="">自動推定</option>
                  {(['information', 'comparison', 'transaction'] as DraftIntent[]).map((intentValue) => (
                    <option key={intentValue} value={intentValue}>
                      {intentValue}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label text="推奨文字数レンジ" />
                <Input name="word_count_range" placeholder="例: 2000-2400" />
              </div>
              <div>
                <Label text="出力形式" required />
                <select
                  name="output_format"
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                  defaultValue="docs"
                  required
                >
                  {outputFormats.map((format) => (
                    <option key={format} value={format}>
                      {format}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="品質チェックRubric" required />
                <select
                  name="quality_rubric"
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                  defaultValue="standard"
                  required
                >
                  {rubrics.map((rubric) => (
                    <option key={rubric} value={rubric}>
                      {rubric}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <Label text="目的・CTA" />
                <Input name="intended_cta" placeholder="例: 資料DL / 相談フォーム" />
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-900">読者ペルソナ</h3>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="職種" required />
                <Input name="persona_job_role" placeholder="例: B2Bマーケティング担当" required />
              </div>
              <div>
                <Label text="経験年数" />
                <Input name="persona_experience_years" placeholder="例: 3-5年" />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="主なニーズ" required />
                <Textarea name="persona_needs" rows={4} placeholder="1行につき1ニーズを記載" required />
              </div>
              <div>
                <Label text="禁則表現" />
                <Textarea name="persona_prohibited_expressions" rows={4} placeholder="1行につき1つのNGワード/表現" />
              </div>
            </div>
          </section>

          <section className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-900">ガイドライン</h3>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="サブキーワード" />
                <Textarea name="supporting_keywords" rows={3} placeholder="カンマまたは改行区切り" />
              </div>
              <div>
                <Label text="既存関連記事ID" />
                <Textarea name="existing_article_ids" rows={3} placeholder="改行区切りで入力" />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="参考URL / 競合例" />
                <Textarea name="reference_urls" rows={3} placeholder="https://example.com を改行区切りで入力" />
              </div>
              <div>
                <Label text="禁止ワード" />
                <Textarea name="forbidden_words" rows={3} placeholder="全角/半角や固有名詞の指定などを1行ずつ" />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="表記ルール" />
                <Textarea name="notation_guidelines" rows={3} placeholder="例: 英数字は半角、固有名詞は正式表記で統一" />
              </div>
              <div>
                <Label text="スタイルガイド ID" />
                <Input name="style_guide_id" placeholder="style-guide-default" />
              </div>
            </div>
            <div>
              <Label text="利用するプロンプトバージョン" />
              <Input name="prompt_version" placeholder="v1" />
            </div>
          </section>

          <section className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-900">見出し構成</h3>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="見出し生成" />
                <select
                  name="heading_mode"
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                  value={headingMode}
                  onChange={(event) => setHeadingMode(event.target.value as HeadingMode)}
                >
                  <option value="auto">自動生成</option>
                  <option value="manual">テンプレート指定</option>
                </select>
              </div>
              <div>
                <p className="text-xs text-slate-500">
                  テンプレート指定では1行につき1つの見出しを入力してください。サンプル: QUEST構成など。
                </p>
              </div>
            </div>
            {headingMode === 'manual' ? (
              <div>
                <Label text="見出しテンプレート" required />
                <Textarea
                  name="heading_overrides"
                  rows={6}
                  placeholder={[
                    'リード：読むべき理由（QUESTのQ/Uで共感）',
                    'まず知るべき要点（結論）',
                    '定義と範囲（Owned/Earned/Paid）',
                    '主要チャネルと役割（SEO/広告/メール/ソーシャル 等）',
                    'KPIの因数分解（例：売上＝流入×CVR×AOV）'
                  ].join('\n')}
                  required
                />
              </div>
            ) : null}
          </section>

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
