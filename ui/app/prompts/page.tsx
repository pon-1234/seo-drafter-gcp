'use client';

import { FormEvent, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Tabs } from '@/components/ui/tabs';

type PromptLayer = 'system' | 'developer' | 'user';

type TemplateInput = Record<PromptLayer, string>;

interface PromptVersionView {
  version: string;
  description?: string;
  createdAt: string;
  templates: TemplateInput;
}

const layerLabels: Record<PromptLayer, string> = {
  system: 'System',
  developer: 'Developer',
  user: 'User'
};

export default function PromptsPage() {
  const [selected, setSelected] = useState<PromptVersionView | null>(null);
  const [templates, setTemplates] = useState<TemplateInput>({
    system: 'あなたはシニアSEO編集者です。',
    developer: '出力は JSON 形式で返してください。',
    user: ''
  });
  const [description, setDescription] = useState('初期バージョン');
  const [version, setVersion] = useState('v1');
  const [versions, setVersions] = useState<PromptVersionView[]>([]);
  const [message, setMessage] = useState<string | null>(null);

  const onSave = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setMessage(null);
    try {
      const payload = {
        prompt_id: 'default-content',
        version,
        description,
        templates: Object.entries(templates).map(([layer, content]) => ({ layer, content })),
        variables: {
          primary_keyword: '{{primary_keyword}}',
          persona: '{{persona.name}}'
        }
      };
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || 'https://seo-drafter-api-yxk2eqrkvq-an.a.run.app';
      const response = await fetch(baseUrl + '/api/prompts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const result = await response.json();
      const next: PromptVersionView = {
        version: result.version,
        description: result.description,
        createdAt: new Date(result.created_at).toLocaleString(),
        templates
      };
      setVersions((prev) => [next, ...prev]);
      setMessage(`バージョン ${result.version} を保存しました`);
    } catch (error) {
      console.error(error);
      setMessage('保存に失敗しました。API 接続を確認してください。');
    }
  };

  const previewTabItems = Object.entries(templates).map(([layer, content]) => ({
    id: layer,
    label: layerLabels[layer as PromptLayer],
    content: (
      <pre className="whitespace-pre-wrap text-sm text-slate-700">
        {content || 'テンプレート未入力'}
      </pre>
    )
  }));

  return (
    <div className="grid gap-6 lg:grid-cols-[2fr,1fr]">
      <Card>
        <CardHeader title="プロンプト編集" description="System / Developer / User 層を分離して管理します。" />
        <form onSubmit={onSave}>
          <CardContent className="space-y-6">
            <div className="grid gap-4 md:grid-cols-3">
              <div>
                <label className="text-sm font-medium text-slate-700">バージョン</label>
                <Input value={version} onChange={(event) => setVersion(event.target.value)} />
              </div>
              <div className="md:col-span-2">
                <label className="text-sm font-medium text-slate-700">説明</label>
                <Input value={description} onChange={(event) => setDescription(event.target.value)} />
              </div>
            </div>
            {(Object.keys(layerLabels) as PromptLayer[]).map((layer) => (
              <div key={layer}>
                <label className="text-sm font-medium text-slate-700">{layerLabels[layer]}</label>
                <Textarea
                  rows={4}
                  value={templates[layer]}
                  onChange={(event) =>
                    setTemplates((prev) => ({
                      ...prev,
                      [layer]: event.target.value
                    }))
                  }
                  placeholder={`例: {{primary_keyword}} を用いて...`}
                />
              </div>
            ))}
            {message ? <p className="text-sm text-slate-600">{message}</p> : null}
          </CardContent>
          <CardFooter>
            <Button type="submit">バージョン保存</Button>
          </CardFooter>
        </form>
      </Card>
      <div className="space-y-6">
        <Card>
          <CardHeader title="テンプレートプレビュー" description="各層の内容を確認できます。" />
          <CardContent>
            <Tabs items={previewTabItems} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader title="保存済みバージョン" description="最新5件を表示します。" />
          <CardContent className="space-y-4">
            {versions.length === 0 ? (
              <p className="text-sm text-slate-500">まだ保存されたバージョンはありません。</p>
            ) : (
              versions.map((item) => (
                <button
                  key={item.version}
                  onClick={() => setSelected(item)}
                  className="flex w-full flex-col rounded-md border border-slate-200 px-3 py-2 text-left text-sm hover:border-primary"
                >
                  <span className="font-medium text-slate-900">{item.version}</span>
                  <span className="text-slate-500">{item.createdAt}</span>
                  <span className="text-slate-600">{item.description}</span>
                </button>
              ))
            )}
          </CardContent>
        </Card>
        {selected ? (
          <Card>
            <CardHeader title={`バージョン ${selected.version}`} description={selected.createdAt} />
            <CardContent className="space-y-4">
              {(Object.keys(selected.templates) as PromptLayer[]).map((layer) => (
                <div key={layer}>
                  <p className="text-xs font-semibold uppercase text-slate-500">{layerLabels[layer]}</p>
                  <p className="whitespace-pre-wrap text-sm text-slate-700">{selected.templates[layer]}</p>
                </div>
              ))}
            </CardContent>
          </Card>
        ) : null}
      </div>
    </div>
  );
}
