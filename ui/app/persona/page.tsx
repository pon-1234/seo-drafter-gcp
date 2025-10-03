'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';

interface Persona {
  name: string;
  job_to_be_done?: string;
  pain_points: string[];
  goals: string[];
  reading_level?: string;
  tone?: string;
  search_intent?: string;
  success_metrics: string[];
}

export default function PersonaPage() {
  const [primaryKeyword, setPrimaryKeyword] = useState('B2B マーケティング');
  const [persona, setPersona] = useState<Persona | null>(null);
  const [overrideJson, setOverrideJson] = useState('');
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const derivePersona = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';
      const response = await fetch(baseUrl + '/api/persona/derive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ primary_keyword: primaryKeyword })
      });
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const body = await response.json();
      setPersona(body.persona);
      setOverrideJson(JSON.stringify(body.persona, null, 2));
    } catch (error) {
      console.error(error);
      setMessage('ペルソナの自動生成に失敗しました。');
    } finally {
      setLoading(false);
    }
  };

  const onLock = () => {
    try {
      const parsed = JSON.parse(overrideJson);
      setPersona(parsed);
      setMessage('ペルソナをロックしました。');
    } catch (error) {
      setMessage('JSON の形式が正しくありません。');
    }
  };

  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr,0.8fr]">
      <Card>
        <CardHeader title="ペルソナ自動生成" description="キーワードに基づき Vertex AI から初期ペルソナを生成します。" />
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-slate-700">主キーワード</label>
            <Input value={primaryKeyword} onChange={(event) => setPrimaryKeyword(event.target.value)} />
          </div>
          <Button type="button" onClick={derivePersona} disabled={loading}>
            {loading ? '生成中...' : '自動生成する'}
          </Button>
          {persona ? (
            <div className="rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <p className="font-semibold text-slate-900">{persona.name}</p>
              <p className="mt-1">JTBD: {persona.job_to_be_done}</p>
              <p className="mt-1">トーン: {persona.tone}</p>
              <p className="mt-2 text-xs uppercase text-slate-500">Pain Points</p>
              <ul className="list-disc pl-5">
                {persona.pain_points.map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </div>
          ) : (
            <p className="text-sm text-slate-500">まだペルソナは生成されていません。</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader title="JSON編集" description="生成結果を微調整し、ロックしてジョブに適用します。" />
        <CardContent>
          <Textarea
            rows={18}
            value={overrideJson}
            onChange={(event) => setOverrideJson(event.target.value)}
            placeholder="{\n  \"name\": ...\n}"
          />
          {message ? <p className="mt-2 text-sm text-slate-600">{message}</p> : null}
        </CardContent>
        <CardFooter>
          <Button type="button" onClick={onLock}>
            JSONをロック
          </Button>
        </CardFooter>
      </Card>
    </div>
  );
}
