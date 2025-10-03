import Link from 'next/link';

const sections = [
  {
    title: 'Brief入力フォーム',
    description: 'キーワード、意図、スタイルガイドを指定して生成ジョブを作成します。',
    href: '/brief'
  },
  {
    title: 'プロンプト管理',
    description: 'System / Developer / User テンプレートを編集し、バージョン固定で保存。',
    href: '/prompts'
  },
  {
    title: 'ペルソナスタジオ',
    description: '自動生成されたペルソナJSONを確認し、上書き・ロックします。',
    href: '/persona'
  },
  {
    title: '生成プレビュー',
    description: 'アウトライン・本文ドラフト・FAQ・Meta・根拠URLを確認。',
    href: '/preview'
  },
  {
    title: '品質チェック',
    description: '重複率、過剰主張、YMYLフラグ、スタイル差分をレビュー。',
    href: '/quality'
  }
];

export default function Home() {
  return (
    <section className="grid gap-6 md:grid-cols-2">
      {sections.map((section) => (
        <Link
          key={section.href}
          href={section.href}
          className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm transition hover:-translate-y-1 hover:border-primary"
        >
          <h2 className="text-lg font-semibold text-slate-900">{section.title}</h2>
          <p className="mt-2 text-sm text-slate-600">{section.description}</p>
        </Link>
      ))}
    </section>
  );
}
