const DEFAULT_API_BASE_URL = 'https://seo-drafter-api-yxk2eqrkvq-an.a.run.app';

type ApiUrlOptions = {
  fallback?: string;
};

export function getApiBaseUrl(options: ApiUrlOptions = {}): string {
  const envValue = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (envValue) {
    return envValue;
  }
  return options.fallback ?? DEFAULT_API_BASE_URL;
}

export function buildApiUrl(path: string, options: ApiUrlOptions = {}): string {
  const baseUrl = getApiBaseUrl(options);
  const normalizedBase = baseUrl.replace(/\/+$/, '');
  const normalizedPath = path.replace(/^\/+/, '');
  return `${normalizedBase}/${normalizedPath}`;
}

export async function apiFetch<T>(
  path: string,
  init?: RequestInit,
  options: ApiUrlOptions = {}
): Promise<T> {
  const response = await fetch(buildApiUrl(path, options), init);
  if (!response.ok) {
    const message = await response.text().catch(() => '');
    throw new Error(message || `Request failed with status ${response.status}`);
  }
  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }

  const text = await response.text().catch(() => '');
  return (text as unknown) as T;
}
