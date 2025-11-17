import React, { useEffect, useMemo, useState } from 'react'
import { analyze, analyzeBatch, health, modelStatus, warmModels, type SentimentResponse } from './lib/api'

const TEXT_LIMIT_DEFAULT = 2500

function useTheme() {
  const [theme, setTheme] = useState<'dark' | 'light'>(() => (localStorage.getItem('theme') as 'dark' | 'light') || 'dark')
  useEffect(() => {
    const root = document.documentElement
    if (theme === 'dark') root.classList.add('dark')
    else root.classList.remove('dark')
    localStorage.setItem('theme', theme)
  }, [theme])
  return { theme, setTheme }
}

function Header({ theme, setTheme }: { theme: 'dark' | 'light'; setTheme: (t: 'dark' | 'light') => void }) {
  return (
    <header className="sticky top-0 z-10 border-b border-base-border bg-base-bg/80 backdrop-blur">
      <div className="mx-auto max-w-6xl px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2.5 h-2.5 rounded-full bg-success animate-pulse" />
          <h1 className="text-lg font-semibold">QuickTone</h1>
          <span className="text-xs text-slate-400 hidden sm:block">Real-time sentiment API</span>
        </div>
        <div className="flex items-center gap-3">
          <ThemeToggle theme={theme} setTheme={setTheme} />
          <a className="btn btn-primary" href="/docs" target="_blank" rel="noreferrer">API Docs</a>
        </div>
      </div>
    </header>
  )
}

function ThemeToggle({ theme, setTheme }: { theme: 'dark' | 'light'; setTheme: (t: 'dark' | 'light') => void }) {
  return (
    <div className="inline-flex items-center gap-2">
      <span className="text-sm text-slate-400">Theme</span>
      <div className="flex rounded-lg border border-base-border overflow-hidden">
        <button className={`px-3 py-1 text-sm ${theme==='dark' ? 'bg-primary-500 text-white' : 'bg-base-bg text-slate-300'}`} onClick={() => setTheme('dark')}>Dark</button>
        <button className={`px-3 py-1 text-sm ${theme==='light' ? 'bg-primary-500 text-white' : 'bg-base-bg text-slate-300'}`} onClick={() => setTheme('light')}>Light</button>
      </div>
    </div>
  )
}

function Stat({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="px-4 py-3 rounded-lg bg-base-bg border border-base-border">
      <div className="text-xs text-slate-400">{label}</div>
      <div className="text-base font-medium">{value}</div>
    </div>
  )
}

function ProgressBar({ progress, total }: { progress: number; total: number }) {
  const pct = total === 0 ? 0 : Math.round((progress / total) * 100)
  return (
    <div className="w-full h-2 bg-base-bg rounded-full overflow-hidden border border-base-border">
      <div className="h-full bg-primary-500 transition-all" style={{ width: `${pct}%` }} />
    </div>
  )
}

export default function App() {
  const { theme, setTheme } = useTheme()
  const [apiKey, setApiKey] = useState('')
  const [text, setText] = useState('I absolutely love this product!')
  const [model, setModel] = useState<'vader' | 'distilbert' | 'distilbert-sst-2' | ''>('')
  const [task, setTask] = useState<'sentiment' | 'emotion'>('sentiment')
  const [threshold, setThreshold] = useState<number | ''>('')
  const [limit, setLimit] = useState<number>(TEXT_LIMIT_DEFAULT)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState<SentimentResponse | null>(null)
  const [showPerf, setShowPerf] = useState(true)
  const [healthInfo, setHealthInfo] = useState<any>(null)
  const [modelInfo, setModelInfo] = useState<any>(null)

  const remaining = useMemo(() => Math.max(0, limit - text.length), [text, limit])
  const overLimit = text.length > limit

  useEffect(() => {
    health().then(setHealthInfo).catch(() => setHealthInfo(null))
    modelStatus().then(setModelInfo).catch(() => setModelInfo(null))
  }, [])

  async function onAnalyze() {
      setLoading(true)
      try {
        const res = await analyze({
          text,
          model: model || undefined,
          task_type: task,
          threshold: threshold === '' ? undefined : threshold,
        }, apiKey || undefined)
        setResult(res)
      } catch (e: any) {
        alert(e.message || 'Request failed')
      } finally {
        setLoading(false)
      }
}

  // Batch demo
  const [batchInput, setBatchInput] = useState('This is great!\nThis is terrible.')
  const batchItems = useMemo(() => batchInput.split('\n').map(s => s.trim()).filter(Boolean), [batchInput])
  const [batchProgress, setBatchProgress] = useState(0)
  const [batchTotal, setBatchTotal] = useState(0)
  const [batchResult, setBatchResult] = useState<SentimentResponse[] | null>(null)

  async function onAnalyzeBatch() {
    setBatchResult(null)
    setBatchProgress(0)
    setBatchTotal(batchItems.length)
    setLoading(true)
    try {
      const res = await analyzeBatch({ texts: batchItems, model: model || undefined, task_type: task, threshold: threshold === '' ? undefined : threshold }, (done, total) => {
        setBatchProgress(done)
        setBatchTotal(total)
      }, apiKey || undefined)
      setBatchResult(res.results)
    } catch (e: any) {
      alert(e.message || 'Batch failed')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen">
      <Header theme={theme} setTheme={setTheme} />

      <main className="mx-auto max-w-6xl px-4 py-6 grid gap-6 md:grid-cols-3">
        <section className="md:col-span-2 grid gap-6">
          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold">Analyze Sentiment</h2>
              <button onClick={() => setShowPerf(v => !v)} className="text-sm text-slate-400 underline">{showPerf ? 'Hide' : 'Show'} performance</button>
            </div>
            <div className="grid gap-3">
              <label className="label">Text</label>
              <textarea className={`textarea min-h-[120px] ${overLimit ? 'border-danger' : ''}`} value={text} onChange={e => setText(e.target.value)} maxLength={5000} placeholder="Type your text here..." />
              <div className="flex items-center justify-between text-xs">
                <span className={overLimit ? 'text-danger' : 'text-slate-400'}>
                  {overLimit ? `Over limit by ${text.length - limit} characters` : `${remaining} characters remaining (limit ${limit})`}
                </span>
                <span className="text-slate-400">Model: {model || healthInfo?.default_model || 'vader'} • Available: {healthInfo?.models_available?.join(', ') || 'vader, distilbert'}</span>
              </div>

              <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3 mt-2">
                <div className="grid gap-1">
                  <label className="label">Model</label>
                  <select className="select" value={model} onChange={e => setModel(e.target.value as any)}>
                    <option value="">Default ({healthInfo?.default_model || 'vader'})</option>
                    <option value="vader">VADER</option>
                    <option value="distilbert">DistilBERT (GoEmotions)</option>
                    <option value="distilbert-sst-2">DistilBERT (SST-2)</option>
                  </select>
                </div>
                <div className="grid gap-1">
                  <label className="label">Task</label>
                  <select className="select" value={task} onChange={e => setTask(e.target.value as any)}>
                    <option value="sentiment">Sentiment</option>
                    <option value="emotion">Emotion</option>
                  </select>
                </div>
                <div className="grid gap-1">
                  <label className="label">Threshold (optional)</label>
                  <input className="input" type="number" min={0} max={1} step={0.01} placeholder="e.g., 0.35" value={threshold} onChange={e => setThreshold(e.target.value === '' ? '' : Number(e.target.value))} />
                </div>
              </div>

                <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3 mt-2">
                    <div className="grid gap-1">
                      <label className="label">API Key (Optional)</label>
                      <input
                        className="input"
                        type="password"
                        placeholder="X-API-Key"
                        value={apiKey}
                        onChange={e => setApiKey(e.target.value)}
                      />
                    </div>
                    <div className="grid gap-1">
                      <label className="label">Text limit</label>
                      <input
                        className="input"
                        type="number"
                        min={1}
                        step={1}
                        value={limit}
                        onChange={e => setLimit(Number(e.target.value) || TEXT_LIMIT_DEFAULT)}
                      />
                    </div>
                    <div className="flex items-end">
                      <button
                        className="btn btn-primary w-full"
                        disabled={loading || overLimit || text.trim().length === 0}
                        onClick={onAnalyze}
                      >
                        {loading ? 'Analyzing…' : 'Analyze'}
                      </button>
                    </div>
                  </div>

                  {/* Small helper link under API key field */}
                  <div className="mt-1 text-[11px] text-slate-400">
                    <a
                      href="https://forms.gle/tWm7cs9kPNz3i6ML7"
                      target="_blank"
                      rel="noreferrer"
                      className="underline underline-offset-2 hover:text-primary-300"
                    >
                      Don&apos;t have an API key? Request one
                    </a>
                  </div>
            </div>

            {result && (
              <div className="mt-5 grid gap-3">
                <div className="text-sm text-slate-300">Prediction</div>
                <div className="grid sm:grid-cols-3 gap-3">
                  <div className="card p-4">
                    <div className="text-xs text-slate-400">Sentiment</div>
                    <div className="text-lg font-semibold">{result.sentiment}</div>
                  </div>
                  <div className="card p-4">
                    <div className="text-xs text-slate-400">Confidence</div>
                    <div className="text-lg font-semibold">{(result.confidence * 100).toFixed(1)}%</div>
                  </div>
                  <div className="card p-4">
                    <div className="text-xs text-slate-400">Model</div>
                    <div className="text-lg font-semibold">{result.model}</div>
                  </div>
                </div>
                {showPerf && (
                  <div className="grid sm:grid-cols-3 gap-3">
                    <Stat label="Processing time" value={<>{result.processing_time_ms} ms</>} />
                    <Stat label="Task type" value={result.task_type} />
                    <Stat label="Text length" value={`${text.length} chars`} />
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="card p-5">
            <div className="flex items-center justify-between mb-4">
              <h2 className="font-semibold">Batch Analysis</h2>
              <button onClick={() => warmModels(apiKey || undefined).then(() => modelStatus().then(setModelInfo))} className="text-sm underline text-slate-300">Warm models</button>
            </div>
            <div className="grid gap-3">
              <label className="label">One item per line</label>
              <textarea className="textarea min-h-[120px]" placeholder={"Great!\nAwful.."} value={batchInput} onChange={e => setBatchInput(e.target.value)} />
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>{batchItems.length} items</span>
                <span>Progress: {batchProgress}/{batchTotal}</span>
              </div>
              <ProgressBar progress={batchProgress} total={batchTotal} />
              <div className="flex justify-end">
                <button className="btn btn-primary" disabled={loading || batchItems.length === 0} onClick={onAnalyzeBatch}>{loading ? 'Processing…' : 'Run batch'}</button>
              </div>
            </div>

            {batchResult && (
              <div className="mt-5 grid gap-3">
                <div className="text-sm text-slate-300">Results</div>
                <div className="grid gap-3">
                  {batchResult.map((r, i) => (
                    <div key={i} className="p-3 rounded-lg border border-base-border bg-base-bg/70 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <span className={`px-2 py-0.5 rounded text-xs border ${r.sentiment === 'positive' ? 'border-success text-success' : r.sentiment === 'negative' ? 'border-danger text-danger' : 'border-slate-500 text-slate-300'}`}>{r.sentiment}</span>
                        <span className="text-sm text-slate-300">{(r.confidence*100).toFixed(1)}%</span>
                      </div>
                      <div className="text-xs text-slate-400">{r.processing_time_ms} ms • {r.model}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </section>

        <aside className="grid gap-6">
          <div className="card p-5">
            <h3 className="font-semibold mb-3">Service Status</h3>
            <div className="grid gap-2 text-sm">
              <div className="flex items-center justify-between"><span className="text-slate-400">Health</span><span className="font-medium">{healthInfo ? 'OK' : 'Unknown'}</span></div>
              <div className="flex items-center justify-between"><span className="text-slate-400">Default model</span><span className="font-medium">{healthInfo?.default_model || 'vader'}</span></div>
              <div className="flex items-center justify-between"><span className="text-slate-400">Version</span><span className="font-medium">{healthInfo?.version || '-'}</span></div>
            </div>
          </div>

            <div className="card p-5">
                <h3 className="font-semibold mb-3">Models</h3>
                <div className="grid gap-2 text-sm">
                    <div className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 items-start">
                        <span className="text-slate-400">Loaded</span>
                        <span className="font-medium break-words">
                          {modelInfo?.loaded_models?.join(', ') || 'vader'}
                        </span>
                    </div>
                    <div className="grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 items-start">
                        <span className="text-slate-400">Default</span>
                        <span className="font-medium break-words">
                      {modelInfo?.default_model || 'vader'}
                    </span>
                    </div>
                </div>
            </div>

          <div className="card p-5">
            <h3 className="font-semibold mb-3">Tips</h3>
            <ul className="list-disc list-inside text-sm text-slate-300 space-y-1">
              <li>Set a model override to compare VADER vs DistilBERT</li>
              <li>Warm models before batch for best latency</li>
              <li>Use API Docs for more parameters</li>
              <li>Anonymous requests are rate-limited</li>
            </ul>
          </div>
        </aside>
      </main>

      <footer className="border-t border-base-border py-6 text-center text-xs text-slate-500">
        Built with FastAPI • React • Tailwind
      </footer>
    </div>
  )
}
