import './globals.css';
import type { Metadata } from 'next';
import { ReactNode } from 'react';

export const metadata: Metadata = {
  title: 'SEO Drafter - Control Center',
  description: 'Plan, generate, and review SEO drafts with Google Cloud orchestration.'
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="ja">
      <body className="min-h-screen">
        <div className="mx-auto flex min-h-screen max-w-6xl flex-col gap-8 px-6 py-8">
          <header className="flex items-center justify-between">
            <h1 className="text-2xl font-semibold text-primary">
              <a href="/">SEO Drafter</a>
            </h1>
            <nav className="flex gap-4 text-sm text-slate-600">
              <a href="/brief" className="hover:text-primary">
                記事作成依頼
              </a>
              <a href="/drafts" className="hover:text-primary">
                生成記事一覧
              </a>
              <a href="/preview" className="hover:text-primary">
                プレビュー
              </a>
              <a href="/prompts" className="hover:text-primary">
                プロンプト管理
              </a>
              <a href="/persona" className="hover:text-primary">
                ペルソナスタジオ
              </a>
              <a href="/persona/templates" className="hover:text-primary">
                テンプレート管理
              </a>
            </nav>
          </header>
          <main className="flex-1">{children}</main>
        </div>
      </body>
    </html>
  );
}
