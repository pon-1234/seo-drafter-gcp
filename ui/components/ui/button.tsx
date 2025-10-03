import { ButtonHTMLAttributes } from 'react';

export function Button({ className = '', ...props }: ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      className={`rounded-md bg-primary px-4 py-2 text-sm font-medium text-white shadow hover:bg-blue-600 ${className}`}
      {...props}
    />
  );
}
