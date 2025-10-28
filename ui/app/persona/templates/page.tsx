'use client';

import { FormEvent, useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { apiFetch } from '@/lib/api';

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

type EditableTemplate = PersonaTemplate & { isNew?: boolean };

const emptyTemplate: EditableTemplate = {
  id: '',
  label: '',
  description: '',
  reader: {
    job_role: '',
    experience_years: '',
    needs: [],
    prohibited_expressions: []
  },
  writer: {
    name: '',
    role: '',
    expertise: '',
    voice: '',
    mission: '',
    qualities: []
  },
  extras: {
    intended_cta: '',
    notation_guidelines: '',
    quality_rubric: '',
    preferred_sources: [],
    reference_media: [],
    supporting_keywords: [],
    reference_urls: []
  },
  heading: {
    mode: 'auto',
    overrides: []
  },
  isNew: true
};

const joinList = (values?: string[] | null) => (values && values.length ? values.join('\n') : '');
const splitList = (value: string) => value.split(/[\r\n]+/).map((line) => line.trim()).filter(Boolean);

export default function PersonaTemplateManagerPage() {
  const [templates, setTemplates] = useState<PersonaTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [formMessage, setFormMessage] = useState<string | null>(null);
  const [listError, setListError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [formState, setFormState] = useState<EditableTemplate>(emptyTemplate);
  const [saving, setSaving] = useState(false);

  const loadTemplates = async () => {
    setLoading(true);
    setListError(null);
    try {
      const data = await apiFetch<PersonaTemplate[]>('api/persona/templates');
      setTemplates(data);
      if (data.length && !selectedId) {
        selectTemplate(data[0]);
      }
    } catch (error) {
      console.error(error);
      setListError('テンプレート一覧の取得に失敗しました。');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadTemplates();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const selectTemplate = (template: PersonaTemplate | null) => {
    if (!template) {
      setSelectedId(null);
      setFormState({ ...emptyTemplate });
      return;
    }
    setSelectedId(template.id);
    setFormState({
      ...template,
      reader: {
        job_role: template.reader?.job_role ?? '',
        experience_years: template.reader?.experience_years ?? '',
        needs: template.reader?.needs ?? [],
        prohibited_expressions: template.reader?.prohibited_expressions ?? []
      },
      writer: {
        name: template.writer?.name ?? '',
        role: template.writer?.role ?? '',
        expertise: template.writer?.expertise ?? '',
        voice: template.writer?.voice ?? '',
        mission: template.writer?.mission ?? '',
        qualities: template.writer?.qualities ?? []
      },
      extras: {
        intended_cta: template.extras?.intended_cta ?? '',
        notation_guidelines: template.extras?.notation_guidelines ?? '',
        quality_rubric: template.extras?.quality_rubric ?? '',
        preferred_sources: template.extras?.preferred_sources ?? [],
        reference_media: template.extras?.reference_media ?? [],
        supporting_keywords: template.extras?.supporting_keywords ?? [],
        reference_urls: template.extras?.reference_urls ?? []
      },
      heading: {
        mode: template.heading?.mode ?? 'auto',
        overrides: template.heading?.overrides ?? []
      },
      isNew: false
    });
    setFormMessage(null);
  };

  const resetForm = () => {
    setSelectedId(null);
    setFormState({ ...emptyTemplate });
    setFormMessage(null);
  };

  const updateField = (path: string, value: string) => {
    setFormState((prev) => {
      const next = { ...prev } as any;
      const parts = path.split('.');
      let cursor = next;
      for (let i = 0; i < parts.length - 1; i += 1) {
        const key = parts[i];
        cursor[key] = cursor[key] ?? {};
        cursor = cursor[key];
      }
      cursor[parts[parts.length - 1]] = value;
      return { ...next };
    });
  };

  const updateListField = (path: string, value: string) => {
    setFormState((prev) => {
      const next = { ...prev } as any;
      const parts = path.split('.');
      let cursor = next;
      for (let i = 0; i < parts.length - 1; i += 1) {
        cursor = cursor[parts[i]];
      }
      cursor[parts[parts.length - 1]] = splitList(value);
      return { ...next };
    });
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!formState.id.trim()) {
      setFormMessage('テンプレートIDは必須です。');
      return;
    }
    if (!formState.label.trim()) {
      setFormMessage('テンプレート名（ラベル）は必須です。');
      return;
    }

    setSaving(true);
    setFormMessage(null);
    try {
      const payload: PersonaTemplate = {
        id: formState.id.trim(),
        label: formState.label.trim(),
        description: formState.description?.trim() || undefined,
        reader: {
          job_role: formState.reader?.job_role?.trim() || undefined,
          experience_years: formState.reader?.experience_years?.trim() || undefined,
          needs: formState.reader?.needs ?? [],
          prohibited_expressions: formState.reader?.prohibited_expressions ?? []
        },
        writer: {
          name: formState.writer?.name?.trim() || undefined,
          role: formState.writer?.role?.trim() || undefined,
          expertise: formState.writer?.expertise?.trim() || undefined,
          voice: formState.writer?.voice?.trim() || undefined,
          mission: formState.writer?.mission?.trim() || undefined,
          qualities: formState.writer?.qualities ?? []
        },
        extras: {
          intended_cta: formState.extras?.intended_cta?.trim() || undefined,
          notation_guidelines: formState.extras?.notation_guidelines?.trim() || undefined,
          quality_rubric: formState.extras?.quality_rubric?.trim() || undefined,
          preferred_sources: formState.extras?.preferred_sources ?? [],
          reference_media: formState.extras?.reference_media ?? [],
          supporting_keywords: formState.extras?.supporting_keywords ?? [],
          reference_urls: formState.extras?.reference_urls ?? []
        },
        heading: {
          mode: formState.heading?.mode ?? 'auto',
          overrides: formState.heading?.overrides ?? []
        }
      };

      const isNew = formState.isNew;
      const endpoint = isNew ? 'api/persona/templates' : `api/persona/templates/${payload.id}`;
      const method = isNew ? 'POST' : 'PUT';

      const saved = await apiFetch<PersonaTemplate>(endpoint, {
        method,
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      await loadTemplates();
      setFormMessage(isNew ? 'テンプレートを追加しました。' : 'テンプレートを更新しました。');
      setFormState({ ...saved, isNew: false });
      setSelectedId(saved.id);
    } catch (error) {
      console.error(error);
      setFormMessage('テンプレートの保存に失敗しました。');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (templateId: string) => {
    if (!window.confirm('このテンプレートを削除しますか？')) {
      return;
    }
    try {
      await apiFetch<void>(`api/persona/templates/${templateId}`, { method: 'DELETE' });
      await loadTemplates();
      if (selectedId === templateId) {
        resetForm();
      }
    } catch (error) {
      console.error(error);
      setFormMessage('テンプレートの削除に失敗しました。');
    }
  };

  const currentOverrides = formState.heading?.overrides ?? [];

  return (
    <div className="grid gap-6 lg:grid-cols-[1fr,1.1fr]">
      <Card>
        <CardHeader
          title="テンプレート一覧"
          description="既存の読者／書き手テンプレートを確認・選択できます。"
        />
        <CardContent className="space-y-3">
          <div className="flex items-center justify-between text-sm text-slate-500">
            {loading ? <span>読み込み中...</span> : <span>{templates.length} 件</span>}
            <div className="flex gap-2">
              <Button type="button" onClick={loadTemplates} variant="secondary">
                再読み込み
              </Button>
              <Button type="button" onClick={resetForm}>
                新規作成
              </Button>
            </div>
          </div>
          {listError ? <p className="text-sm text-red-500">{listError}</p> : null}
          <div className="space-y-2">
            {templates.map((template) => (
              <button
                key={template.id}
                type="button"
                onClick={() => selectTemplate(template)}
                className={`w-full rounded-md border px-3 py-3 text-left text-sm transition hover:border-primary hover:bg-primary/5 ${
                  selectedId === template.id ? 'border-primary bg-primary/5' : 'border-slate-200'
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-slate-900">{template.label}</span>
                  <span className="text-xs text-slate-500">{template.id}</span>
                </div>
                {template.description ? (
                  <p className="mt-1 text-xs text-slate-500">{template.description}</p>
                ) : null}
                <div className="mt-2 flex flex-wrap gap-2 text-xs text-slate-500">
                  {template.reader?.job_role ? <span>読者: {template.reader.job_role}</span> : null}
                  {template.writer?.name ? <span>書き手: {template.writer.name}</span> : null}
                  <span>Heading: {template.heading?.mode ?? 'auto'}</span>
                </div>
                <div className="mt-2 flex gap-2">
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={(event) => {
                      event.stopPropagation();
                      selectTemplate(template);
                    }}
                  >
                    編集
                  </Button>
                  <Button
                    type="button"
                    variant="danger"
                    onClick={(event) => {
                      event.stopPropagation();
                      handleDelete(template.id);
                    }}
                  >
                    削除
                  </Button>
                </div>
              </button>
            ))}
            {!loading && templates.length === 0 ? (
              <p className="text-sm text-slate-500">登録されているテンプレートがありません。</p>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader
          title={formState.isNew ? 'テンプレートを作成' : `テンプレートを編集 (${formState.id})`}
          description="ヒアリングの標準化に必要な読者・書き手情報を管理します。"
        />
        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-6 text-sm">
            <section className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">基本情報</h3>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label text="テンプレートID" required />
                  <Input
                    value={formState.id}
                    onChange={(event) => updateField('id', event.target.value)}
                    placeholder="例: b2b-saas-akari"
                    disabled={!formState.isNew}
                    required
                  />
                </div>
                <div>
                  <Label text="テンプレート名" required />
                  <Input
                    value={formState.label}
                    onChange={(event) => updateField('label', event.target.value)}
                    placeholder="例: B2B SaaS リード獲得"
                    required
                  />
                </div>
              </div>
              <div>
                <Label text="説明" />
                <Textarea
                  rows={2}
                  value={formState.description || ''}
                  onChange={(event) => updateField('description', event.target.value)}
                  placeholder="用途や想定読者などを簡潔に記載"
                />
              </div>
            </section>

            <section className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">読者ペルソナ</h3>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label text="職種" />
                  <Input
                    value={formState.reader?.job_role || ''}
                    onChange={(event) => updateField('reader.job_role', event.target.value)}
                    placeholder="例: B2Bマーケティングマネージャー"
                  />
                </div>
                <div>
                  <Label text="経験年数" />
                  <Input
                    value={formState.reader?.experience_years || ''}
                    onChange={(event) => updateField('reader.experience_years', event.target.value)}
                    placeholder="例: 3-5年"
                  />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label text="主なニーズ (改行区切り)" />
                  <Textarea
                    rows={3}
                    value={joinList(formState.reader?.needs)}
                    onChange={(event) => updateListField('reader.needs', event.target.value)}
                    placeholder={'顧客課題を列挙\n例: ナーチャリング歩留まり改善'}
                  />
                </div>
                <div>
                  <Label text="禁則表現" />
                  <Textarea
                    rows={3}
                    value={joinList(formState.reader?.prohibited_expressions)}
                    onChange={(event) => updateListField('reader.prohibited_expressions', event.target.value)}
                    placeholder={'避けたいワードを列挙\n例: 初心者向け'}
                  />
                </div>
              </div>
            </section>

            <section className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">書き手ペルソナ</h3>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label text="書き手名" />
                  <Input
                    value={formState.writer?.name || ''}
                    onChange={(event) => updateField('writer.name', event.target.value)}
                    placeholder="例: 井上あかり"
                  />
                </div>
                <div>
                  <Label text="役割 / ポジション" />
                  <Input
                    value={formState.writer?.role || ''}
                    onChange={(event) => updateField('writer.role', event.target.value)}
                    placeholder="例: B2B SaaS コンテンツストラテジスト"
                  />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label text="専門領域・強み" />
                  <Textarea
                    rows={3}
                    value={formState.writer?.expertise || ''}
                    onChange={(event) => updateField('writer.expertise', event.target.value)}
                    placeholder="例: 施策連携分析、データドリブンSEO"
                  />
                </div>
                <div>
                  <Label text="声のトーン / 文体" />
                  <Textarea
                    rows={3}
                    value={formState.writer?.voice || ''}
                    onChange={(event) => updateField('writer.voice', event.target.value)}
                    placeholder="例: 共感とロジックを両立"
                  />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label text="ミッション" />
                  <Textarea
                    rows={3}
                    value={formState.writer?.mission || ''}
                    onChange={(event) => updateField('writer.mission', event.target.value)}
                    placeholder="例: 読者の迷いを解き行動を促す"
                  />
                </div>
                <div>
                  <Label text="大切にするスタイル (改行区切り)" />
                  <Textarea
                    rows={3}
                    value={joinList(formState.writer?.qualities)}
                    onChange={(event) => updateListField('writer.qualities', event.target.value)}
                    placeholder={'数値で裏付ける\n意外性のある事例を入れる'}
                  />
                </div>
              </div>
            </section>

            <section className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">ガイドライン</h3>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label text="想定CTA" />
                  <Input
                    value={formState.extras?.intended_cta || ''}
                    onChange={(event) => updateField('extras.intended_cta', event.target.value)}
                    placeholder="例: 資料請求"
                  />
                </div>
                <div>
                  <Label text="品質Rubric" />
                  <Input
                    value={formState.extras?.quality_rubric || ''}
                    onChange={(event) => updateField('extras.quality_rubric', event.target.value)}
                    placeholder="例: standard"
                  />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label text="表記ルール" />
                  <Textarea
                    rows={3}
                    value={formState.extras?.notation_guidelines || ''}
                    onChange={(event) => updateField('extras.notation_guidelines', event.target.value)}
                    placeholder="例: 英数字は半角で統一"
                  />
                </div>
                <div>
                  <Label text="優先参照メディア (改行区切り)" />
                  <Textarea
                    rows={3}
                    value={joinList(formState.extras?.reference_media)}
                    onChange={(event) => updateListField('extras.reference_media', event.target.value)}
                  />
                </div>
              </div>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label text="優先参照ソース / URL" />
                  <Textarea
                    rows={3}
                    value={joinList(formState.extras?.preferred_sources)}
                    onChange={(event) => updateListField('extras.preferred_sources', event.target.value)}
                  />
                </div>
                <div>
                  <Label text="参考URL (改行区切り)" />
                  <Textarea
                    rows={3}
                    value={joinList(formState.extras?.reference_urls)}
                    onChange={(event) => updateListField('extras.reference_urls', event.target.value)}
                  />
                </div>
              </div>
              <div>
                <Label text="サポートキーワード (改行区切り)" />
                <Textarea
                  rows={3}
                  value={joinList(formState.extras?.supporting_keywords)}
                  onChange={(event) => updateListField('extras.supporting_keywords', event.target.value)}
                />
              </div>
            </section>

            <section className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wide text-slate-500">見出しテンプレート</h3>
              <div className="grid gap-3 md:grid-cols-2">
                <div>
                  <Label text="生成モード" />
                  <select
                    className="w-full rounded-md border border-slate-200 px-3 py-2 text-sm shadow-sm focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/30"
                    value={formState.heading?.mode || 'auto'}
                    onChange={(event) =>
                      setFormState((prev) => ({
                        ...prev,
                        heading: {
                          mode: event.target.value as HeadingMode,
                          overrides: prev.heading?.overrides ?? []
                        }
                      }))
                    }
                  >
                    <option value="auto">自動生成</option>
                    <option value="manual">固定テンプレート</option>
                  </select>
                </div>
                <div>
                  <Label text="見出しリスト (改行区切り)" />
                  <Textarea
                    rows={formState.heading?.mode === 'manual' ? 4 : 2}
                    value={joinList(currentOverrides)}
                    onChange={(event) =>
                      setFormState((prev) => ({
                        ...prev,
                        heading: {
                          mode: prev.heading?.mode ?? 'auto',
                          overrides: splitList(event.target.value)
                        }
                      }))
                    }
                    placeholder={'イントロダクション\n課題の提示\n成功事例'}
                    disabled={formState.heading?.mode !== 'manual'}
                  />
                </div>
              </div>
            </section>

            {formMessage ? <p className="text-sm text-slate-600">{formMessage}</p> : null}
          </CardContent>
          <CardFooter className="flex items-center justify-between">
            {!formState.isNew ? (
              <Button
                type="button"
                variant="secondary"
                onClick={() => selectTemplate(formState)}
              >
                編集内容を再読み込み
              </Button>
            ) : (
              <span />
            )}
            <div className="flex gap-2">
              <Button type="button" variant="secondary" onClick={resetForm}>
                クリア
              </Button>
              <Button type="submit" disabled={saving}>
                {saving ? '保存中...' : formState.isNew ? 'テンプレートを追加' : 'テンプレートを更新'}
              </Button>
            </div>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}

function Label({ text, required = false }: { text: string; required?: boolean }) {
  return (
    <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-slate-600">
      {text}
      {required ? <span className="ml-1 text-[10px] font-normal text-red-500">必須</span> : null}
    </label>
  );
}
