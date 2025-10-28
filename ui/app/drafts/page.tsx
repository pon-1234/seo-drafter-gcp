'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import { apiFetch } from '@/lib/api';

interface DraftListItem {
  draft_id: string;
  job_id: string;
  status: string;
  created_at: string | null;
  title: string | null;
  article_type: string | null;
  primary_keyword: string | null;
}

interface DraftListResponse {
  drafts: DraftListItem[];
  total: number;
}

export default function DraftsListPage() {
  const [drafts, setDrafts] = useState<DraftListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchDrafts();
  }, []);

  const fetchDrafts = async () => {
    try {
      setLoading(true);
      const data = await apiFetch<DraftListResponse>('api/drafts', undefined, {
        fallback: 'http://localhost:8080'
      });
      setDrafts(data.drafts);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unknown error');
    } finally {
      setLoading(false);
    }
  };

  const getStatusColor = (status: string) => {
    if (status === 'completed') return 'bg-green-100 text-green-800';
    if (status === 'processing') return 'bg-blue-100 text-blue-800';
    if (status === 'failed') return 'bg-red-100 text-red-800';
    return 'bg-gray-100 text-gray-800';
  };

  const formatDate = (dateString: string | null) => {
    if (!dateString) return 'N/A';
    try {
      return new Date(dateString).toLocaleString('ja-JP');
    } catch {
      return dateString;
    }
  };

  return (
    <div className="container mx-auto p-6">
      <div className="mb-8">
        <h1 className="text-3xl font-bold mb-2">生成記事一覧</h1>
        <p className="text-gray-600">Firestoreに保存されている記事の一覧です</p>
      </div>

      {loading && (
        <div className="text-center py-8">
          <p className="mt-2 text-gray-600">読み込み中...</p>
        </div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 text-red-700 px-4 py-3 rounded mb-4">
          エラー: {error}
        </div>
      )}

      {!loading && !error && drafts.length === 0 && (
        <div className="bg-yellow-50 border border-yellow-200 text-yellow-700 px-4 py-3 rounded">
          記事がまだありません
        </div>
      )}

      {!loading && !error && drafts.length > 0 && (
        <div className="bg-white shadow-md rounded-lg overflow-hidden">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">タイトル</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">キーワード</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">記事タイプ</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">ステータス</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">作成日時</th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">操作</th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {drafts.map((draft) => (
                <tr key={draft.draft_id} className="hover:bg-gray-50">
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-gray-900">{draft.title || 'タイトルなし'}</div>
                    <div className="text-xs text-gray-500">ID: {draft.draft_id.substring(0, 8)}...</div>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-900">{draft.primary_keyword || '-'}</td>
                  <td className="px-6 py-4 text-sm text-gray-900">{draft.article_type || '-'}</td>
                  <td className="px-6 py-4">
                    <span className={'px-2 text-xs rounded-full ' + getStatusColor(draft.status)}>
                      {draft.status}
                    </span>
                  </td>
                  <td className="px-6 py-4 text-sm text-gray-500">{formatDate(draft.created_at)}</td>
                  <td className="px-6 py-4 text-sm">
                    <Link href={'/preview?draft_id=' + draft.draft_id} className="text-indigo-600 hover:text-indigo-900">
                      プレビュー
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <div className="mt-8">
        <Link href="/" className="inline-block bg-gray-600 text-white px-6 py-2 rounded hover:bg-gray-700">
          ← ホームに戻る
        </Link>
      </div>
    </div>
  );
}
