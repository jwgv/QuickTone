export type SentimentRequest = {
  text: string
  model?: 'vader' | 'distilbert' | 'distilbert-sst-2'
  task_type?: 'sentiment' | 'emotion'
  threshold?: number
}

export type SentimentResponse = {
  model: 'vader' | 'distilbert' | 'distilbert-sst-2'
  sentiment: string
  confidence: number
  processing_time_ms: number
  task_type: 'sentiment' | 'emotion'
  text?: string
}

export type BatchSentimentRequest = {
  texts: string[]
  model?: 'vader' | 'distilbert' | 'distilbert-sst-2'
  task_type?: 'sentiment' | 'emotion'
  threshold?: number
}

export type BatchSentimentResponse = {
  results: SentimentResponse[]
  total_processing_time_ms: number
  items_processed: number
}

const API_BASE = (import.meta.env.VITE_API_BASE as string) || ''

function headers(apiKey?: string) {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (apiKey) h['X-API-Key'] = apiKey
  return h
}

export async function health() {
  const res = await fetch(`${API_BASE}/health`)
  if (!res.ok) throw new Error('Health check failed')
  const data = (await res.json()) as any
  return data
}

export async function modelStatus() {
  const res = await fetch(`${API_BASE}/api/v1/models/status`)
  if (!res.ok) throw new Error('Model status failed')
  return res.json() as Promise<any>
}

export async function warmModels(
  models?: ('distilbert' | 'distilbert-sst-2' | 'vader')[],
  apiKey?: string
) {
  const res = await fetch(`${API_BASE}/api/v1/models/warm`, {
    method: 'POST',
    headers: headers(apiKey),
    body: JSON.stringify(
      models && models.length > 0
        ? { models }        // e.g. { models: ["distilbert", "distilbert-sst-2"] }
        : {}                // or omit list to let backend pick defaults
    ),
  })
  if (!res.ok) throw new Error('Warm up failed')
  return res.json() as Promise<{ models_loaded: string[]; warm_up_time_ms: number }>
}

export async function analyze(req: SentimentRequest, apiKey?: string) {
  const res = await fetch(`${API_BASE}/api/v1/sentiment`, {
    method: 'POST',
    headers: headers(apiKey),
    body: JSON.stringify(req)
  })
  if (!res.ok) {
    const msg = await res.text()
    throw new Error(msg || 'Request failed')
  }
  return res.json() as Promise<SentimentResponse>
}

export async function analyzeBatch(
  req: BatchSentimentRequest,
  onProgress?: (done: number, total: number) => void,
  apiKey?: string
) {
  onProgress?.(0, req.texts.length)
  const res = await fetch(`${API_BASE}/api/v1/sentiment/batch`, {
    method: 'POST',
    headers: headers(apiKey),
    body: JSON.stringify(req)
  })
  if (!res.ok) {
    const msg = await res.text()
    throw new Error(msg || 'Batch request failed')
  }
  onProgress?.(req.texts.length, req.texts.length)
  return res.json() as Promise<BatchSentimentResponse>
}
