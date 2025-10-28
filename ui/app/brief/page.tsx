'use client';

import { FormEvent, useEffect, useMemo, useRef, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { apiFetch } from '@/lib/api';

type DraftIntent = 'information' | 'comparison' | 'transaction';
type ArticleType = 'information' | 'comparison' | 'ranking' | 'closing';
type OutputFormat = 'docs' | 'html';
type HeadingMode = 'auto' | 'manual';

type PersonaTemplate = {
  id: string;
  label: string;
  description?: string;
  reader?: {
    job_role?: string;
    experience_years?: string;
    needs?: string[];
    prohibited_expressions?: string[];
  };
  writer?: {
    name?: string;
    role?: string;
    expertise?: string;
    voice?: string;
    mission?: string;
    qualities?: string[];
  };
  extras?: {
    intended_cta?: string;
    notation_guidelines?: string;
    quality_rubric?: string;
    preferred_sources?: string[];
    reference_media?: string[];
    supporting_keywords?: string[];
    reference_urls?: string[];
  };
  heading?: {
    mode: HeadingMode;
    overrides?: string[];
  };
};

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
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');
  const formRef = useRef<HTMLFormElement>(null);
  const [personaTemplates, setPersonaTemplates] = useState<PersonaTemplate[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState<boolean>(false);
  const [templateError, setTemplateError] = useState<string | null>(null);

  const articleTypes: ArticleType[] = useMemo(() => ['information', 'comparison', 'ranking', 'closing'], []);
  const outputFormats: OutputFormat[] = useMemo(() => ['docs', 'html'], []);
  const rubrics = useMemo(() => ['standard', 'eeat-focused', 'originality-plus'], []);

  useEffect(() => {
    const controller = new AbortController();
    const loadTemplates = async () => {
      setTemplatesLoading(true);
      setTemplateError(null);
      try {
        const data = await apiFetch<PersonaTemplate[]>(
          'api/persona/templates',
          { signal: controller.signal }
        );
        setPersonaTemplates(data);
      } catch (error) {
        if ((error as Error).name !== 'AbortError') {
          console.error(error);
          setTemplateError('テンプレートの取得に失敗しました。');
        }
      } finally {
        setTemplatesLoading(false);
      }
    };

    loadTemplates();
    return () => controller.abort();
  }, []);

  const parseList = (value: FormDataEntryValue | null, mode: 'flex' | 'newline' = 'flex'): string[] => {
    if (!value) return [];
    const text = String(value);
    const pattern = mode === 'newline' ? /[\r\n]+/ : /[\r\n,、，]+/;
    return text
      .split(pattern)
      .map((item) => item.trim())
      .filter(Boolean);
  };

  const applyTemplate = (templateId: string) => {
    if (!formRef.current) return;
    const template = personaTemplates.find((item) => item.id === templateId);
    if (!template) {
      setStatus('テンプレートが見つかりませんでした。');
      return;
    }

    const form = formRef.current;

    const setValue = (name: string, value?: string) => {
      const element = form.elements.namedItem(name) as
        | HTMLInputElement
        | HTMLTextAreaElement
        | HTMLSelectElement
        | null;
      if (element) {
        element.value = value ?? '';
      }
    };

    if (template.reader) {
      setValue('persona_job_role', template.reader.job_role);
      setValue('persona_experience_years', template.reader.experience_years);
      setValue('persona_needs', (template.reader.needs || []).join('\n'));
      setValue(
        'persona_prohibited_expressions',
        (template.reader.prohibited_expressions || []).join('\n')
      );
    }

    if (template.writer) {
      setValue('writer_name', template.writer.name);
      setValue('writer_role', template.writer.role);
      setValue('writer_expertise', template.writer.expertise);
      setValue('writer_voice', template.writer.voice);
      setValue('writer_mission', template.writer.mission);
      setValue('writer_qualities', (template.writer.qualities || []).join('\n'));
    }

    if (template.extras) {
      setValue('intended_cta', template.extras.intended_cta);
      setValue('notation_guidelines', template.extras.notation_guidelines);
      setValue('quality_rubric', template.extras.quality_rubric);
      setValue('preferred_sources', (template.extras.preferred_sources || []).join('\n'));
      setValue('reference_media', (template.extras.reference_media || []).join('\n'));
      setValue('supporting_keywords', (template.extras.supporting_keywords || []).join('\n'));
      setValue('reference_urls', (template.extras.reference_urls || []).join('\n'));
    }

    if (template.heading) {
      setHeadingMode(template.heading.mode);
      const headingField = form.elements.namedItem('heading_mode') as
        | HTMLSelectElement
        | HTMLInputElement
        | null;
      if (headingField) {
        headingField.value = template.heading.mode;
      }
      setValue('heading_overrides', (template.heading.overrides || []).join('\n'));
    }

    setStatus(`テンプレート「${template.label}」を適用しました。`);
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

      const writerName = (form.get('writer_name') as string)?.trim();
      const writerPersona = writerName
        ? {
            name: writerName,
            role: ((form.get('writer_role') as string) || '').trim() || undefined,
            expertise: ((form.get('writer_expertise') as string) || '').trim() || undefined,
            voice: ((form.get('writer_voice') as string) || '').trim() || undefined,
            mission: ((form.get('writer_mission') as string) || '').trim() || undefined,
            qualities: parseList(form.get('writer_qualities'), 'newline'),
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
        writer_persona: writerPersona,
        heading_directive: {
          mode: headingModeValue,
          headings: headingModeValue === 'manual' ? parseList(form.get('heading_overrides'), 'newline') : [],
        },
        reference_urls: parseList(form.get('reference_urls'), 'newline'),
        preferred_sources: parseList(form.get('preferred_sources'), 'newline'),
        reference_media: parseList(form.get('reference_media'), 'newline'),
        project_template_id: ((form.get('project_template_id') as string) || '').trim() || undefined,
      };

      const body = await apiFetch<{ id: string }>('api/jobs', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setStatus(`ジョブ作成に成功しました: ${body.id}`);
      formElement.reset();
      setHeadingMode('auto');
      setSelectedTemplate('');
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
      <form ref={formRef} onSubmit={onSubmit}>
        <CardContent className="space-y-8">
          <section className="space-y-4">
            <h3 className="text-sm font-semibold text-slate-900">テンプレート適用</h3>
            <div className="grid gap-4 md:grid-cols-[2fr_auto] items-end">
              <div className="space-y-2">
                <Label text="テンプレート" />
                <select
                  name="persona_template"
                  value={selectedTemplate}
                  onChange={(event) => {
                    setSelectedTemplate(event.target.value);
                    setStatus(null);
                  }}
                  className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                  disabled={templatesLoading || personaTemplates.length === 0}
                >
                  <option value="">{templatesLoading ? '読み込み中…' : 'テンプレートを選択してください'}</option>
                  {personaTemplates.map((template) => (
                    <option key={template.id} value={template.id}>
                      {template.label}
                    </option>
                  ))}
                </select>
              </div>
              <Button
                type="button"
                variant="secondary"
                onClick={() => applyTemplate(selectedTemplate)}
                disabled={!selectedTemplate || personaTemplates.length === 0}
              >
                テンプレートを適用
              </Button>
            </div>
            {templateError ? (
              <p className="text-xs text-red-500">{templateError}</p>
            ) : personaTemplates.length === 0 && !templatesLoading ? (
              <p className="text-xs text-slate-500">テンプレートが登録されていません。Firestore に追加するとここに表示されます。</p>
            ) : selectedTemplate ? (
              <p className="text-xs text-slate-500">
                選択したテンプレートの値でフォームが上書きされます。変更後に必要に応じて微調整してください。
              </p>
            ) : null}
          </section>

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
            <h3 className="text-sm font-semibold text-slate-900">書き手ペルソナ</h3>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="書き手名" />
                <Input name="writer_name" placeholder="例: 井上あかり" />
              </div>
              <div>
                <Label text="役割 / ポジション" />
                <Input name="writer_role" placeholder="例: B2B SaaS コンテンツストラテジスト" />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="専門領域・強み" />
                <Textarea
                  name="writer_expertise"
                  rows={3}
                  placeholder="例: 施策連携によるコンテンツ設計、データドリブンSEO 等"
                />
              </div>
              <div>
                <Label text="声のトーン / 文体キーワード" />
                <Textarea
                  name="writer_voice"
                  rows={3}
                  placeholder="例: 共感とロジックを両立、VAKで情景を伝える 等"
                />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="ミッション / 伝えたい価値" />
                <Textarea
                  name="writer_mission"
                  rows={3}
                  placeholder="例: 読者の迷いを解き、即行動できる自信を届ける"
                />
              </div>
              <div>
                <Label text="大切にするスタイル（1行1項目）" />
                <Textarea
                  name="writer_qualities"
                  rows={3}
                  placeholder="例: 数字と一次情報で裏付け\n意外性のある事例を必ず入れる"
                />
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
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="優先参照メディア / 媒体" />
                <Textarea name="reference_media" rows={3} placeholder="例: Think with Google, HubSpotブログ" />
              </div>
              <div>
                <Label text="優先参照ソース（ドメイン / URL）" />
                <Textarea name="preferred_sources" rows={3} placeholder="例: https://www.meti.go.jp/, https://www.stat.go.jp/" />
              </div>
            </div>
            <div className="grid gap-4 md:grid-cols-2">
              <div>
                <Label text="プロジェクトテンプレート ID" />
                <Input name="project_template_id" placeholder="例: default-benefit-template" />
              </div>
              <div>
                <Label text="利用するプロンプトバージョン" />
                <Input name="prompt_version" placeholder="v1" />
              </div>
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
                    'リード：{keyword}で解決できる課題と得られる成果（QUEST）',
                    '即効性のあるベネフィットと活用シナリオ',
                    '施策連携で描く活用マップと優先タスク',
                    '投資対効果と意外性のある成功・失敗事例',
                    'CTAで導く次のアクションと顧客便益'
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
