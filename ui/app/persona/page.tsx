'use client';

import { FormEvent, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardFooter, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { apiFetch } from '@/lib/api';

interface PersonaProfile {
  name: string;
  job_to_be_done?: string;
  pain_points: string[];
  goals: string[];
  reading_level?: string;
  tone?: string;
  search_intent?: string;
  success_metrics: string[];
}

const emptyPersona: PersonaProfile = {
  name: '',
  pain_points: [],
  goals: [],
  success_metrics: []
};

const PLACEHOLDER_JSON = `{
  "name": "比較検討中のB2Bマーケ担当",
  "job_to_be_done": "自社の見込み客獲得効率を上げたい",
  "pain_points": ["予算制約", "社内承認の難しさ"],
  "goals": ["短期でのCV増"],
  "reading_level": "中級",
  "tone": "信頼できる・実務的",
  "search_intent": "比較",
  "success_metrics": ["CVR", "CAC"]
}`;

export default function PersonaPage() {
  const [primaryKeyword, setPrimaryKeyword] = useState('B2B マーケティング');
  const [persona, setPersona] = useState<PersonaProfile | null>(null);
  const [editorValue, setEditorValue] = useState(PLACEHOLDER_JSON);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleDerive = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const { persona: derived } = await apiFetch<{ persona: PersonaProfile }>('api/persona/derive', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ primary_keyword: primaryKeyword })
      });
      setPersona(derived);
      setEditorValue(JSON.stringify(derived, null, 2));
      setMessage('ペルソナを取得しました。必要に応じて編集してください。');
    } catch (error) {
      console.error(error);
      setMessage('ペルソナの自動生成に失敗しました。');
    } finally {
      setLoading(false);
    }
  };

  const handleLock = (event: FormEvent) => {
    event.preventDefault();
    try {
      const parsed = JSON.parse(editorValue) as PersonaProfile;
      setPersona(parsed);
      setMessage('ペルソナをロックしました。Brief入力で利用できます。');
    } catch (error) {
      console.error(error);
      setMessage('JSON の形式が正しくありません。');
    }
  };

  const display = persona ?? emptyPersona;

  return (
    <div className="grid gap-6 lg:grid-cols-[1.2fr,0.8fr]">
      <Card>
        <CardHeader
          title="ペルソナ自動生成"
          description="キーワードに基づき OpenAI から初期ペルソナを生成します。"
        />
        <CardContent className="space-y-4">
          <div>
            <label className="text-sm font-medium text-slate-700">主キーワード</label>
            <Input value={primaryKeyword} onChange={(event) => setPrimaryKeyword(event.target.value)} />
          </div>
          <Button type="button" onClick={handleDerive} disabled={loading}>
            {loading ? '生成中...' : '自動生成する'}
          </Button>
          {persona ? (
            <div className="space-y-3 rounded-md border border-slate-200 bg-slate-50 p-4 text-sm text-slate-700">
              <div>
                <p className="text-sm font-semibold text-slate-900">{display.name || '未設定'}</p>
                <p className="text-xs text-slate-500">Tone: {display.tone || '未設定'}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-slate-500">JTBD</p>
                <p>{display.job_to_be_done || '未設定'}</p>
              </div>
              <div>
                <p className="text-xs uppercase text-slate-500">Pain Points</p>
                <ul className="list-disc pl-5">
                  {display.pain_points.length ? (
                    display.pain_points.map((item) => <li key={item}>{item}</li>)
                  ) : (
                    <li className="list-none text-slate-500">未設定</li>
                  )}
                </ul>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-500">まだペルソナは生成されていません。</p>
          )}
        </CardContent>
      </Card>
      <Card>
        <CardHeader title="JSON編集" description="生成結果を微調整し、ロックしてジョブに適用します。" />
        <form onSubmit={handleLock}>
          <CardContent>
            <Textarea
              rows={20}
              value={editorValue}
              onChange={(event) => setEditorValue(event.target.value)}
              placeholder={PLACEHOLDER_JSON}
            />
            {message ? <p className="mt-2 text-sm text-slate-600">{message}</p> : null}
          </CardContent>
          <CardFooter>
            <Button type="submit">JSONをロック</Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}
