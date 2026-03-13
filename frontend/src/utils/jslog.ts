/**
 * Frontend JS logger — buffers log entries and flushes to /api/logs/js.
 * Also writes to browser console.
 *
 * Usage:
 *   import { jslog } from '../utils/jslog'
 *   jslog.info('PAWWidget', 'Widget loaded', { cube: 'gl_pln' })
 *   jslog.error('CubeViewer', 'MDX failed', { mdx, error: e.message })
 */

type LogLevel = 'debug' | 'info' | 'warn' | 'error'

interface LogEntry {
  level: LogLevel
  message: string
  source: string
  data?: Record<string, unknown>
}

const FLUSH_INTERVAL = 3000 // ms
const MAX_BUFFER = 50

let buffer: LogEntry[] = []
let flushTimer: ReturnType<typeof setTimeout> | null = null

function scheduleFlush() {
  if (flushTimer) return
  flushTimer = setTimeout(flush, FLUSH_INTERVAL)
}

async function flush() {
  flushTimer = null
  if (buffer.length === 0) return
  const batch = buffer.splice(0, MAX_BUFFER)
  try {
    const token = localStorage.getItem('klikk_access_token')
    await fetch('/api/logs/js', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ entries: batch }),
    })
  } catch {
    // If flush fails, re-add to buffer (drop if too large)
    if (buffer.length < 200) buffer.unshift(...batch)
  }
  if (buffer.length > 0) scheduleFlush()
}

function log(level: LogLevel, source: string, message: string, data?: Record<string, unknown>) {
  // Console output
  const tag = `[${source}]`
  const consoleFn = level === 'error' ? console.error : level === 'warn' ? console.warn : console.log
  consoleFn(tag, message, data ?? '')

  // Buffer for server
  buffer.push({ level, message, source, data })
  if (buffer.length >= MAX_BUFFER) {
    flush()
  } else {
    scheduleFlush()
  }
}

export const jslog = {
  debug: (source: string, msg: string, data?: Record<string, unknown>) => log('debug', source, msg, data),
  info: (source: string, msg: string, data?: Record<string, unknown>) => log('info', source, msg, data),
  warn: (source: string, msg: string, data?: Record<string, unknown>) => log('warn', source, msg, data),
  error: (source: string, msg: string, data?: Record<string, unknown>) => log('error', source, msg, data),
  /** Force flush all buffered entries now */
  flush,
}

// Capture uncaught errors
if (typeof window !== 'undefined') {
  window.addEventListener('error', (e) => {
    jslog.error('window', `Uncaught: ${e.message}`, {
      filename: e.filename,
      lineno: e.lineno,
      colno: e.colno,
    })
  })
  window.addEventListener('unhandledrejection', (e) => {
    jslog.error('window', `Unhandled rejection: ${e.reason}`)
  })
}
