import { ReactNode } from 'react';

export function Card({ children }: { children: ReactNode }) {
  return <div className="rounded-lg border border-slate-200 bg-white shadow-sm">{children}</div>;
}

export function CardHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="border-b border-slate-200 px-6 py-4">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {description ? <p className="mt-1 text-sm text-slate-600">{description}</p> : null}
    </div>
  );
}

export function CardContent({ children }: { children: ReactNode }) {
  return <div className="px-6 py-4">{children}</div>;
}

export function CardFooter({ children }: { children: ReactNode }) {
  return <div className="flex items-center justify-end gap-2 px-6 py-4">{children}</div>;
}
