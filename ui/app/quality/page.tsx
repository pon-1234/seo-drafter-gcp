'use client';

import { FormEvent, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Input } from '@/components/ui/input';

interface Job {
  id: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  workflow_execution_id?: string;
  created_at: string;
  updated_at: string;
}

export default function QualityPage() {
  const [jobId, setJobId] = useState('');
  const [job, setJob] = useState<Job | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setJob(null);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL ?? '';
      const response = await fetch(baseUrl + `/api/jobs/${jobId}`);
      if (!response.ok) {
        throw new Error(await response.text());
      }
      const json = await response.json();
      setJob(json);
    } catch (err) {
      console.error(err);
      setError('ジョブが見つかりませんでした。');
    }
  };

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader title="品質チェック" description="ジョブの進捗と品質ゲート通過状況を確認します。" />
        <CardContent>
          <form className="flex gap-3" onSubmit={onSubmit}>
            <Input value={jobId} onChange={(event) => setJobId(event.target.value)} placeholder="job-id" />
            <Button type="submit">ジョブ検索</Button>
          </form>
          {error ? <p className="mt-4 text-sm text-red-500">{error}</p> : null}
        </CardContent>
      </Card>
      {job ? (
        <Card>
          <CardHeader title="ジョブ詳細" />
          <CardContent className="space-y-3 text-sm text-slate-700">
            <p>
              <span className="font-medium text-slate-600">状態:</span> {job.status}
            </p>
            <p>
              <span className="font-medium text-slate-600">作成日時:</span> {new Date(job.created_at).toLocaleString()}
            </p>
            <p>
              <span className="font-medium text-slate-600">更新日時:</span> {new Date(job.updated_at).toLocaleString()}
            </p>
            {job.workflow_execution_id ? (
              <p>
                <span className="font-medium text-slate-600">Workflow Execution:</span> {job.workflow_execution_id}
              </p>
            ) : null}
            <p className="rounded-md border border-slate-200 bg-slate-50 p-3">
              再現性: 同一プロンプトと seed で再実行すると同じ出力となるよう、Firestone にプロンプトとモデル設定を保存します。
            </p>
          </CardContent>
        </Card>
      ) : null}
    </div>
  );
}
