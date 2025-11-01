import { NextRequest } from 'next/server'
import { db } from '@/lib/db'

const FALLBACK_STORE_ID = 'ikebukuro'
const VALID_STORE_CACHE = new Map<string, boolean>()

async function storeExists(storeId: string): Promise<boolean> {
  if (!storeId) return false

  if (VALID_STORE_CACHE.has(storeId)) {
    return VALID_STORE_CACHE.get(storeId) ?? false
  }

  const store = await db.store.findUnique({
    where: { id: storeId },
    select: { id: true },
  })

  const exists = Boolean(store)
  VALID_STORE_CACHE.set(storeId, exists)
  return exists
}

function extractStoreCandidate(request: NextRequest): string | null {
  const searchParams = request.nextUrl.searchParams
  const paramStoreId = searchParams.get('storeId') ?? searchParams.get('store')
  if (paramStoreId) {
    return paramStoreId
  }

  const headerStoreId =
    request.headers.get('x-store-id') ??
    request.headers.get('x-store-code') ??
    request.headers.get('x-tenant-id')
  if (headerStoreId) {
    return headerStoreId
  }

  const hostname = request.nextUrl.hostname || request.headers.get('host') || ''
  if (hostname) {
    const plainHost = hostname.split(':')[0]
    const segments = plainHost.split('.')
    if (segments.length > 2) {
      return segments[0]
    }
  }

  return null
}

export async function resolveStoreId(request: NextRequest): Promise<string> {
  const candidate = extractStoreCandidate(request)
  const normalized = candidate?.trim().toLowerCase()
  if (normalized && (await storeExists(normalized))) {
    return normalized
  }
  return FALLBACK_STORE_ID
}

export async function ensureStoreId(storeId: string | null | undefined): Promise<string> {
  const normalized = storeId?.trim().toLowerCase()
  if (normalized && (await storeExists(normalized))) {
    return normalized
  }
  if (!(await storeExists(FALLBACK_STORE_ID))) {
    await db.store.upsert({
      where: { id: FALLBACK_STORE_ID },
      update: {},
      create: {
        id: FALLBACK_STORE_ID,
        name: '池袋店',
        displayName: 'サロン池袋店',
        slug: FALLBACK_STORE_ID,
      },
    })
    VALID_STORE_CACHE.set(FALLBACK_STORE_ID, true)
  }
  return FALLBACK_STORE_ID
}

