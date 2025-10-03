'use client';

import { ReactNode, useState } from 'react';

export interface TabItem {
  id: string;
  label: string;
  content: ReactNode;
}

export function Tabs({ items }: { items: TabItem[] }) {
  const [active, setActive] = useState(items[0]?.id);
  return (
    <div>
      <div className="mb-3 flex gap-2 border-b border-slate-200">
        {items.map((item) => (
          <button
            key={item.id}
            onClick={() => setActive(item.id)}
            className={`rounded-t-md px-4 py-2 text-sm font-medium ${
              active === item.id ? 'bg-white text-primary shadow-inner' : 'text-slate-500'
            }`}
          >
            {item.label}
          </button>
        ))}
      </div>
      <div className="rounded-md border border-slate-200 bg-white p-4">
        {items.find((item) => item.id === active)?.content}
      </div>
    </div>
  );
}
