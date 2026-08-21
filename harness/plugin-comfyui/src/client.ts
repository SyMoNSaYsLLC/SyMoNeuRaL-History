/**
 * ComfyUI REST and websocket execution client — deliverable 2.
 *
 * Every route, status code and frame layout below was transcribed from `references/ComfyUI`
 * and cites the line it came from. Nothing is recalled from general knowledge of ComfyUI, and
 * where the reference disagrees with the obvious guess the reference wins and the surprise is
 * written down next to the method.
 *
 * ## Compliance, stated once and not re-asserted
 *
 * Like `types.ts` and `plugin.ts`, this file **imports** `@deepseek-ai/cordis` as a runtime
 * dependency and therefore does not meet `PROJECT-TASKS.md` #89's "nothing imported" bar. That
 * was argued once in the header of `types.ts` and is not re-argued here. It is flagged rather
 * than omitted because a fresh file is exactly where a retracted claim gets quietly retyped.
 *
 * ## This client has not been run
 *
 * There is still no `package.json` and no `tsconfig.json` under `harness/plugin-comfyui/`, so
 * nothing here has been through `tsc`, let alone against a live engine. Every figure this file
 * could have carried — a latency, a frame count, a round-trip — is absent for that reason. The
 * transcriptions are checkable against the reference tree; the behaviour is not yet checkable
 * at all, and this comment is the honest form of that gap rather than a promise to fix it.
 *
 * ## Which websocket
 *
 * The global. The harness declares `"engines": {"node": "^22.19.0 || >=24.0.0"}`
 * (`references/deepseek-harness/package.json:8-10`), where `WebSocket` is a standard global, and
 * its own client code uses the global directly —
 * `packages/client/connection/src/client/web-api-client.ts:42`, `const socket = new
 * WebSocket(url)`. The `ws` package in `packages/client/connection/package.json:42` is **not**
 * counter-evidence: its only consumer is
 * `packages/client/connection/src/websocket-downlink.ts:6`, which imports `WebSocketServer` and
 * calls `handleUpgrade`. That is a server, and a server is not precedent for a client.
 *
 * The catch, recorded because it will bite whoever runs this first: **this box is on node
 * v20.19.2, where `typeof WebSocket === 'undefined'`.** `fetch`, `AbortSignal.any` and
 * `AbortSignal.timeout` all exist there, so the REST half would run today and the socket half
 * would not. {@link requireWebSocket} turns that into one legible error naming the versions
 * instead of a bare `WebSocket is not defined`.
 */

import type { Context } from '@deepseek-ai/cordis'

import {
  COMFY_BINARY_EVENT,
  ClientId,
  PromptId,
  type ComfyBinaryEventId,
  type ComfyBinaryFrame,
  type ComfyHistory,
  type ComfyNodeDefinition,
  type ComfyNodeError,
  type ComfyNodeErrorReason,
  type ComfyObjectInfo,
  type ComfyPromptError,
  type ComfyPromptOutcome,
  type ComfyPromptRequest,
  type ComfyPromptResponse,
  type ComfyQueueState,
  type ComfySystemStats,
  type ComfyTelemetryFrame,
  type ResolvedComfyConfig,
} from './types.ts'

/* ------------------------------------------------------------------ errors */

/**
 * The request never produced a response: DNS, connection refused, timeout, or the lifetime
 * signal firing during teardown. Distinct from {@link ComfyHttpError}, which means the engine
 * answered and said no.
 */
export class ComfyTransportError extends Error {
  readonly method: string
  readonly url: string

  constructor(method: string, url: string, cause: unknown) {
    super(`comfyui: ${method} ${url} did not complete (${renderThrown(cause)})`, { cause })
    this.name = 'ComfyTransportError'
    this.method = method
    this.url = url
  }
}

/** The engine answered with a non-2xx status. */
export class ComfyHttpError extends Error {
  readonly method: string
  readonly url: string
  readonly status: number
  /** Response body as text, truncated. Present because ComfyUI puts the useful part there. */
  readonly body: string

  constructor(method: string, url: string, status: number, body: string) {
    super(`comfyui: ${method} ${url} answered ${status}${body ? ` — ${body}` : ''}`)
    this.name = 'ComfyHttpError'
    this.method = method
    this.url = url
    this.status = status
    this.body = body
  }
}

/**
 * The engine answered 2xx with a body that is not what the route documents.
 *
 * Worth a class of its own rather than folding into {@link ComfyHttpError}: a 200 carrying the
 * wrong document usually means the endpoint is not the engine at all — a proxy error page, a
 * login redirect, a different service on the port — and that is a different thing to debug than
 * a refusal.
 */
export class ComfyProtocolError extends Error {
  readonly url: string

  constructor(url: string, detail: string) {
    super(`comfyui: ${url} answered 200 but ${detail}`)
    this.name = 'ComfyProtocolError'
    this.url = url
  }
}

/**
 * `POST /prompt` refused the graph.
 *
 * Blueprint: `references/ComfyUI/server.py:1098-1104`, `:1135-1136` and `:1138-1144` — all
 * three refusal paths answer 400 with the same `{error: {type, message, details, extra_info},
 * node_errors}` document. The parsed body is carried on {@link detail} so a caller can act on
 * `error.type` without re-parsing a string.
 */
export class ComfyPromptRejectedError extends ComfyHttpError {
  readonly detail: ComfyPromptError

  constructor(url: string, status: number, detail: ComfyPromptError) {
    super('POST', url, status, `${detail.error.type}: ${detail.error.message}`)
    this.name = 'ComfyPromptRejectedError'
    this.detail = detail
  }
}

/* ------------------------------------------------------------------ helpers */

/** Render anything a `catch` can bind for a log line, without assuming it is an `Error`. */
function renderThrown(value: unknown): string {
  if (value instanceof Error) return value.message
  return String(value)
}

/**
 * The `WebSocket` constructor, or a legible failure.
 *
 * See the file header for why this is a global lookup rather than a `ws` import, and why the
 * lookup can fail on this particular box.
 */
function requireWebSocket(): typeof WebSocket {
  const ctor = (globalThis as { WebSocket?: typeof WebSocket }).WebSocket
  if (ctor === undefined) {
    throw new Error(
      'comfyui: no global WebSocket. The harness declares node ^22.19.0 || >=24.0.0 ' +
        '(references/deepseek-harness/package.json:8-10), where it is standard; this ' +
        'interpreter is older. Upgrade node rather than adding a websocket dependency — the ' +
        "harness's own client uses the global (packages/client/connection/src/client/web-api-client.ts:42).",
    )
  }
  return ctor
}

/** Sleep, cut short by `signal`. Never rejects — an aborted wait is a completed wait here. */
function delay(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise<void>(resolve => {
    const finish = (): void => {
      clearTimeout(timer)
      signal.removeEventListener('abort', finish)
      resolve()
    }
    const timer = setTimeout(finish, ms)
    signal.addEventListener('abort', finish, { once: true })
    if (signal.aborted) finish()
  })
}

/** Is this the `{type, data}` envelope every text frame uses? `server.py:287`. */
function isTelemetryFrame(value: unknown): value is ComfyTelemetryFrame {
  if (typeof value !== 'object' || value === null) return false
  return typeof (value as { type?: unknown }).type === 'string' && 'data' in value
}

/** Shape check for `GET /system_stats`. `server.py:686`. */
function isSystemStats(value: unknown): value is ComfySystemStats {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as { system?: unknown; devices?: unknown }
  if (typeof candidate.system !== 'object' || candidate.system === null) return false
  return Array.isArray(candidate.devices)
}

/** Shape check for `POST /prompt`'s success body. `server.py:1132`. */
function isPromptResponse(value: unknown): value is { prompt_id: string; number: number; node_errors?: unknown } {
  if (typeof value !== 'object' || value === null) return false
  const candidate = value as { prompt_id?: unknown; number?: unknown }
  return typeof candidate.prompt_id === 'string' && typeof candidate.number === 'number'
}

/** Shape check for the 400 body shared by every `POST /prompt` refusal. */
function isPromptErrorEnvelope(value: unknown): value is { error: ComfyPromptError['error']; node_errors?: unknown } {
  if (typeof value !== 'object' || value === null) return false
  const error = (value as { error?: unknown }).error
  if (typeof error !== 'object' || error === null) return false
  return typeof (error as { type?: unknown }).type === 'string'
}

/**
 * Turn whatever arrived in `node_errors` into {@link ComfyNodeError} records, checking rather
 * than asserting.
 *
 * This function exists because the two shape checks above are deliberately shallow — they
 * establish enough to route the response and nothing more — and a predicate that *claimed*
 * `Record<string, ComfyNodeError>` on that evidence would be a lie the compiler then believes
 * everywhere downstream. `node_errors` is the field the tool layer reasons about hardest (it
 * is the difference between a clean run and a partial one), so it is the last field that
 * should be taken on trust.
 *
 * Malformed entries are **kept, not dropped**. An entry the server sent and this client cannot
 * parse is still evidence that a node was rejected; discarding it would turn a partial
 * acceptance back into a clean one, which is the exact misreport this typing was added to
 * prevent. Such an entry is normalised to an empty `errors` list with `class_type: 'unknown'`
 * and the raw value preserved under the reason's `extra_info.raw`.
 */
function readNodeErrors(value: unknown): Record<string, ComfyNodeError> {
  const out: Record<string, ComfyNodeError> = {}
  if (typeof value !== 'object' || value === null) return out
  for (const [nodeId, raw] of Object.entries(value as Record<string, unknown>)) {
    if (typeof raw !== 'object' || raw === null) {
      out[nodeId] = unparsedNodeError(raw)
      continue
    }
    const record = raw as { errors?: unknown; dependent_outputs?: unknown; class_type?: unknown }
    if (!Array.isArray(record.errors)) {
      out[nodeId] = unparsedNodeError(raw)
      continue
    }
    out[nodeId] = {
      errors: record.errors.map(readNodeErrorReason),
      dependent_outputs: Array.isArray(record.dependent_outputs)
        ? record.dependent_outputs.filter((id): id is string => typeof id === 'string')
        : [],
      class_type: typeof record.class_type === 'string' ? record.class_type : 'unknown',
    }
  }
  return out
}

/** One `errors[]` entry, with every field defaulted rather than assumed. `execution.py:905`. */
function readNodeErrorReason(value: unknown): ComfyNodeErrorReason {
  if (typeof value !== 'object' || value === null) {
    return { type: 'unparsed', message: String(value), details: '', extra_info: { raw: value } }
  }
  const record = value as Partial<ComfyNodeErrorReason> & { extra_info?: unknown }
  return {
    type: typeof record.type === 'string' ? record.type : 'unparsed',
    message: typeof record.message === 'string' ? record.message : '',
    details: typeof record.details === 'string' ? record.details : '',
    extra_info:
      typeof record.extra_info === 'object' && record.extra_info !== null
        ? (record.extra_info as Record<string, unknown>)
        : {},
  }
}

/** A `node_errors` entry this client could not parse, preserved rather than discarded. */
function unparsedNodeError(raw: unknown): ComfyNodeError {
  return {
    errors: [
      {
        type: 'unparsed',
        message: 'comfyui returned a node_errors entry in an unrecognised shape',
        details: 'expected {errors, dependent_outputs, class_type} per execution.py:1219-1223',
        extra_info: { raw },
      },
    ],
    dependent_outputs: [],
    class_type: 'unknown',
  }
}

/** Pull `prompt_id` off a frame payload without asserting the rest of its shape. */
function readPromptId(data: unknown): string | undefined {
  if (typeof data !== 'object' || data === null) return undefined
  const id = (data as { prompt_id?: unknown }).prompt_id
  return typeof id === 'string' ? id : undefined
}

/** Name a binary event id for a log line. Unknown ids render as their number. */
function binaryEventName(event: ComfyBinaryEventId): string {
  for (const [name, id] of Object.entries(COMFY_BINARY_EVENT)) {
    if (id === event) return name
  }
  return `unknown(${event})`
}

/* --------------------------------------------------------------- reconnect */

/**
 * Reconnect policy, as module constants rather than config fields.
 *
 * Deliberately not added to {@link ResolvedComfyConfig}: the build directive bars inventing
 * configuration properties, and no reference file defines these. They are constants with their
 * reasoning attached, which can become config the day someone needs them to differ.
 *
 * Ten attempts over exponential backoff capped at 15 s is about two and a half minutes of
 * retrying — long enough to ride out a ComfyUI restart (`scripts/comfyui.sh` waits on a VRAM
 * drain, so a restart here is tens of seconds, not milliseconds), short enough that a socket
 * pointed at a dead port gives up and says so instead of retrying until the process exits.
 */
const RECONNECT_BASE_MS = 500
const RECONNECT_MAX_MS = 15_000
const RECONNECT_MAX_ATTEMPTS = 10

/** How long a response body may be before a log line truncates it. */
const MAX_BODY_CHARS = 2_000

/* ------------------------------------------------------------------ client */

/** Options accepted by {@link ComfyClient.waitForPrompt}. */
export interface WaitForPromptOptions {
  /** Override the config timeout for this wait, in milliseconds. */
  timeoutMs?: number
  /** Give up early. Produces an `unconfirmed` outcome, never a rejection. */
  signal?: AbortSignal
}

/** Options accepted by {@link ComfyClient.history}. */
export interface HistoryQuery {
  /** Cap the number of records returned. `server.py:1048`. */
  maxItems?: number
  /**
   * Skip this many records. Defaults to `-1` server-side, which is not "no offset": with
   * `maxItems` set, a negative offset is rewritten to `len(history) - max_items`
   * (`execution.py:1369-1370`), i.e. it means *the last N*. Leave it alone unless paging.
   */
  offset?: number
}

/**
 * One waiter parked on {@link ComfyClient.waitForPrompt}.
 *
 * @internal
 */
interface PromptWaiter {
  promptId: string
  settle: (outcome: ComfyPromptOutcome) => void
}

/**
 * The ComfyUI REST and telemetry client.
 *
 * One instance owns one socket and every HTTP call to one engine. It is constructed by
 * {@link ComfyBridge} in `plugin.ts` and takes that service's lifetime signal, so fiber
 * teardown cancels in-flight requests and stops the reconnect loop without a second mechanism.
 *
 * **It does not mutate graphs and does not roll anything back.** Graph mutation and the
 * `autoRollback` policy that reacts to `execution_error` are deliverable 3 (`tools.ts`); this
 * layer is transport, and keeping the split means the thing that decides *what* to send is
 * testable without a socket.
 */
export class ComfyClient {
  readonly config: ResolvedComfyConfig

  private readonly ctx: Context
  private readonly lifetime: AbortSignal
  private readonly waiters = new Set<PromptWaiter>()

  private socket: WebSocket | undefined
  private pumping = false

  /**
   * The session id this client is actually known by, learned from the connect frame.
   *
   * **This is load-bearing and the reason it is a field rather than a local.** With
   * `config.clientId` empty — the default — the server mints a fresh id per connection
   * (`server.py:278`). Telemetry for a running prompt is routed to the `client_id` recorded in
   * that prompt's `extra_data` (`:1117-1118`), and the reconnect replay at `:289` only fires when
   * the reconnecting `sid` equals the one that owns the run. So a socket blip that reconnects
   * under a *new* id sends every subsequent frame for the in-flight prompt to a session nobody
   * is listening on: the UI renders its scaffold and then receives nothing, with no error
   * anywhere to read.
   *
   * That failure has already happened once in this repository, in a different transport —
   * `desktop-client/SMOKE.md` — and it cost a day. Capturing the minted id here and reusing it
   * on every reconnect *and* on every queued prompt is what prevents it.
   */
  private sessionId: ClientId | undefined

  constructor(ctx: Context, config: ResolvedComfyConfig, lifetime: AbortSignal) {
    this.ctx = ctx
    this.config = config
    this.lifetime = lifetime
    this.sessionId = config.clientId
  }

  /**
   * The client id telemetry will be routed to, or `undefined` before the first connect frame
   * when none was configured.
   */
  get clientId(): ClientId | undefined {
    return this.sessionId
  }

  /** Is the telemetry socket open right now? */
  get connected(): boolean {
    return this.socket !== undefined && this.socket.readyState === this.socket.OPEN
  }

  /* ---------------------------------------------------------------- HTTP */

  /**
   * Compose the deadline for one request.
   *
   * Three signals, all of which must be able to cancel it: the service lifetime (teardown),
   * the configured timeout, and any per-call signal. `AbortSignal.any` is the composition and
   * `AbortSignal.timeout` is the clock; both exist on node 20 and up, so unlike the socket
   * half this works on the current interpreter.
   */
  private deadline(caller: AbortSignal | undefined): AbortSignal {
    const signals: AbortSignal[] = [this.lifetime, AbortSignal.timeout(this.config.timeoutMs)]
    if (caller !== undefined) signals.push(caller)
    return AbortSignal.any(signals)
  }

  /** Issue one request, translating a transport failure into {@link ComfyTransportError}. */
  private async send(
    method: string,
    path: string,
    body: unknown | undefined,
    caller: AbortSignal | undefined,
  ): Promise<Response> {
    const url = `${this.config.endpoint}${path}`
    const headers: Record<string, string> = { accept: 'application/json' }
    const init: RequestInit = { method, headers, signal: this.deadline(caller) }
    if (body !== undefined) {
      headers['content-type'] = 'application/json'
      init.body = JSON.stringify(body)
    }
    try {
      return await fetch(url, init)
    } catch (error) {
      throw new ComfyTransportError(method, url, error)
    }
  }

  /** Read a response body as text, truncated, never throwing. For error paths only. */
  private static async bodyText(response: Response): Promise<string> {
    try {
      const text = await response.text()
      return text.length > MAX_BODY_CHARS ? `${text.slice(0, MAX_BODY_CHARS)}…` : text
    } catch {
      return ''
    }
  }

  /** GET a JSON document, checking the status and the decode but not the shape. */
  private async getJson(path: string, caller: AbortSignal | undefined): Promise<unknown> {
    const response = await this.send('GET', path, undefined, caller)
    const url = `${this.config.endpoint}${path}`
    if (!response.ok) {
      throw new ComfyHttpError('GET', url, response.status, await ComfyClient.bodyText(response))
    }
    try {
      return await response.json()
    } catch (error) {
      throw new ComfyProtocolError(url, `its body is not JSON (${renderThrown(error)})`)
    }
  }

  /**
   * POST to a route that answers a bare 200 with no body, and read nothing.
   *
   * `POST /queue` (`server.py:1146-1158`), `POST /interrupt` (`:1160-1190`) and `POST /free`
   * (`:1192-1201`) all end in `return web.Response(status=200)`. **Calling `.json()` on any of
   * them throws** — there is no document to decode, and treating them like the other routes is
   * a failure that only shows up at runtime.
   */
  private async postNoContent(path: string, body: unknown, caller: AbortSignal | undefined): Promise<void> {
    const response = await this.send('POST', path, body, caller)
    if (!response.ok) {
      const url = `${this.config.endpoint}${path}`
      throw new ComfyHttpError('POST', url, response.status, await ComfyClient.bodyText(response))
    }
    // Drain rather than ignore: an undrained body can hold the connection open.
    await ComfyClient.bodyText(response)
  }

  /* ------------------------------------------------------------ discovery */

  /**
   * `GET /system_stats` — the discovery probe. `references/ComfyUI/server.py:686`.
   *
   * Cheap, present on every build, queues nothing and needs no graph, which is what makes it
   * safe to call at plugin start.
   */
  async systemStats(signal?: AbortSignal): Promise<ComfySystemStats> {
    const body = await this.getJson('/system_stats', signal)
    if (!isSystemStats(body)) {
      throw new ComfyProtocolError(
        `${this.config.endpoint}/system_stats`,
        'the body has no `system` object and `devices` array — this may not be a ComfyUI engine',
      )
    }
    return body
  }

  /**
   * `GET /features` — the server's feature flags over HTTP. `references/ComfyUI/server.py:739`.
   *
   * The same document the websocket negotiation returns, without needing a socket. Left
   * untyped past `Record<string, unknown>`: the contents are the server's to define and this
   * plugin does not interpret them.
   */
  async features(signal?: AbortSignal): Promise<Record<string, unknown>> {
    const body = await this.getJson('/features', signal)
    if (typeof body !== 'object' || body === null) {
      throw new ComfyProtocolError(`${this.config.endpoint}/features`, 'the body is not an object')
    }
    return body as Record<string, unknown>
  }

  /* ----------------------------------------------------------- node metadata */

  /** `GET /object_info` — every registered node class. `references/ComfyUI/server.py:800`. */
  async objectInfo(signal?: AbortSignal): Promise<ComfyObjectInfo> {
    const body = await this.getJson('/object_info', signal)
    if (typeof body !== 'object' || body === null) {
      throw new ComfyProtocolError(`${this.config.endpoint}/object_info`, 'the body is not an object')
    }
    return body as ComfyObjectInfo
  }

  /**
   * `GET /object_info/{node_class}` — one node class. `references/ComfyUI/server.py:813`.
   *
   * The route answers with the same **map** shape as the full document, keyed by class name,
   * rather than with the definition alone — so this unwraps it. An unknown class yields an
   * empty map and a 200, which becomes a {@link ComfyProtocolError} here rather than silently
   * returning `undefined`: asking for a node that does not exist is a caller bug worth raising.
   */
  async objectInfoFor(nodeClass: string, signal?: AbortSignal): Promise<ComfyNodeDefinition> {
    const path = `/object_info/${encodeURIComponent(nodeClass)}`
    const body = await this.getJson(path, signal)
    if (typeof body !== 'object' || body === null) {
      throw new ComfyProtocolError(`${this.config.endpoint}${path}`, 'the body is not an object')
    }
    const definition = (body as Record<string, ComfyNodeDefinition | undefined>)[nodeClass]
    if (definition === undefined) {
      throw new ComfyProtocolError(
        `${this.config.endpoint}${path}`,
        `it does not contain a definition for ${nodeClass} — no such node class is registered`,
      )
    }
    return definition
  }

  /* ------------------------------------------------------------------ queue */

  /**
   * `GET /prompt` — queue depth only. `references/ComfyUI/server.py:747`.
   *
   * Named `queueInfo` rather than `prompt` because the path is misleading: a GET on `/prompt`
   * returns `get_queue_info()` (`:1283-1287`) and has nothing to do with submitting one.
   */
  async queueInfo(signal?: AbortSignal): Promise<{ exec_info: { queue_remaining: number } }> {
    const body = await this.getJson('/prompt', signal)
    if (typeof body !== 'object' || body === null) {
      throw new ComfyProtocolError(`${this.config.endpoint}/prompt`, 'the body is not an object')
    }
    return body as { exec_info: { queue_remaining: number } }
  }

  /** `GET /queue` — what is running and what is pending. `references/ComfyUI/server.py:1064`. */
  async queueState(signal?: AbortSignal): Promise<ComfyQueueState> {
    const body = await this.getJson('/queue', signal)
    if (typeof body !== 'object' || body === null) {
      throw new ComfyProtocolError(`${this.config.endpoint}/queue`, 'the body is not an object')
    }
    return body as ComfyQueueState
  }

  /**
   * `POST /prompt` — queue a graph. `references/ComfyUI/server.py:1072-1144`.
   *
   * **`client_id` is filled in from {@link sessionId} when the caller does not supply one**,
   * which is the whole point of tracking it. Without it the run's telemetry is addressed to
   * whatever id the server last minted for this socket, and after a reconnect that is not the
   * id this client is listening on. See {@link sessionId}.
   *
   * Two things about the response that are easy to get wrong:
   *
   * - **Success carries `node_errors`** (`:1132`). A prompt can be accepted *and* carry
   *   per-node complaints, so an empty-object check on that field is a real assertion.
   * - A 400 is not a transport failure. It is the engine reading the graph and refusing it,
   *   and it comes back as {@link ComfyPromptRejectedError} with the parsed reason attached.
   */
  async queuePrompt(request: ComfyPromptRequest, signal?: AbortSignal): Promise<ComfyPromptResponse> {
    const payload: ComfyPromptRequest = { ...request }
    if (payload.client_id === undefined && this.sessionId !== undefined) {
      payload.client_id = this.sessionId
    }
    if (payload.client_id === undefined) {
      this.ctx.logger.warn(
        'comfyui: queueing a prompt with no client_id — no socket has connected yet, so this ' +
          "run's telemetry cannot be routed back. Poll /history/{prompt_id} for its outcome.",
      )
    }

    const url = `${this.config.endpoint}/prompt`
    const response = await this.send('POST', '/prompt', payload, signal)

    if (!response.ok) {
      let parsed: unknown
      try {
        parsed = await response.json()
      } catch {
        throw new ComfyHttpError('POST', url, response.status, '')
      }
      if (isPromptErrorEnvelope(parsed)) {
        throw new ComfyPromptRejectedError(url, response.status, {
          error: parsed.error,
          node_errors: readNodeErrors(parsed.node_errors),
        })
      }
      throw new ComfyHttpError('POST', url, response.status, JSON.stringify(parsed).slice(0, MAX_BODY_CHARS))
    }

    let body: unknown
    try {
      body = await response.json()
    } catch (error) {
      throw new ComfyProtocolError(url, `its body is not JSON (${renderThrown(error)})`)
    }
    if (!isPromptResponse(body)) {
      throw new ComfyProtocolError(url, 'the body has no `prompt_id` and `number`')
    }
    return {
      prompt_id: PromptId(body.prompt_id),
      number: body.number,
      node_errors: readNodeErrors(body.node_errors),
    }
  }

  /**
   * `POST /queue` with `{clear: true}` — drop everything pending.
   * `references/ComfyUI/server.py:1146-1158`. Returns a bare 200; see {@link postNoContent}.
   *
   * This does **not** stop the run in progress. `clear` empties the pending queue only;
   * interrupting the executing prompt is {@link interrupt}.
   */
  async clearQueue(signal?: AbortSignal): Promise<void> {
    await this.postNoContent('/queue', { clear: true }, signal)
  }

  /**
   * `POST /queue` with `{delete: [...]}` — drop specific pending prompts.
   * `references/ComfyUI/server.py:1146-1158`.
   *
   * Deleting an id that is not queued is not an error there: the handler removes what matches
   * and answers 200 either way, so a 200 does not mean anything was removed. Read
   * {@link queueState} if that distinction matters.
   */
  async deleteQueued(promptIds: readonly string[], signal?: AbortSignal): Promise<void> {
    await this.postNoContent('/queue', { delete: [...promptIds] }, signal)
  }

  /**
   * `POST /interrupt` — stop the running prompt.
   * `references/ComfyUI/server.py:1160-1190`.
   *
   * Omitting `promptId` issues a **global** interrupt, which stops whatever is executing —
   * including a render this plugin did not queue. On a box where the GPU is a single contended
   * resource that is a real hazard, so the parameter is not optional by accident: pass the id
   * unless a global stop is genuinely what is wanted.
   *
   * **A 200 is not proof of interruption.** A targeted interrupt for a prompt that is not
   * currently running matches nothing and still answers 200. Confirm through
   * {@link waitForPrompt} or {@link historyFor}, not through the status code.
   */
  async interrupt(promptId?: string, signal?: AbortSignal): Promise<void> {
    const body = promptId === undefined ? {} : { prompt_id: promptId }
    await this.postNoContent('/interrupt', body, signal)
  }

  /**
   * `POST /free` — unload models and/or free VRAM.
   * `references/ComfyUI/server.py:1192-1201`.
   *
   * **A body is always sent, even when both flags are false.** The handler calls
   * `await request.json()` unguarded, so an empty body raises inside it — unlike
   * `/interrupt`, which catches `json.JSONDecodeError` and carries on. Two neighbouring
   * routes, two different tolerances.
   *
   * This is what `scripts/comfyui.sh stop` POSTs before waiting on a VRAM drain. The process
   * exiting is not the memory coming back, and the next tenant OOMs at step 0 — see
   * `.claude/CLAUDE.md`. Calling this does not perform that wait.
   */
  async free(options: { unloadModels?: boolean; freeMemory?: boolean } = {}, signal?: AbortSignal): Promise<void> {
    await this.postNoContent(
      '/free',
      { unload_models: options.unloadModels ?? false, free_memory: options.freeMemory ?? false },
      signal,
    )
  }

  /* ---------------------------------------------------------------- history */

  /**
   * `GET /history` — finished runs. `references/ComfyUI/server.py:1045-1057`.
   *
   * See {@link HistoryQuery.offset} for the one genuinely surprising parameter.
   */
  async history(query: HistoryQuery = {}, signal?: AbortSignal): Promise<ComfyHistory> {
    const params = new URLSearchParams()
    if (query.maxItems !== undefined) params.set('max_items', String(query.maxItems))
    if (query.offset !== undefined) params.set('offset', String(query.offset))
    const query = params.toString()
    const suffix = query.length > 0 ? `?${query}` : ''
    const body = await this.getJson(`/history${suffix}`, signal)
    if (typeof body !== 'object' || body === null) {
      throw new ComfyProtocolError(`${this.config.endpoint}/history`, 'the body is not an object')
    }
    return body as ComfyHistory
  }

  /**
   * `GET /history/{prompt_id}` — one run's record.
   * `references/ComfyUI/server.py:1059-1062`, over `execution.py:1381-1389`.
   *
   * **Returns a map, not a record**, keyed by prompt id — the single-prompt form wraps its
   * result the same way the full listing does. And **an unknown prompt id is `{}` with a
   * 200**, not a 404, so absence has to be read from the document rather than from the status.
   */
  async historyFor(promptId: string, signal?: AbortSignal): Promise<ComfyHistory> {
    const path = `/history/${encodeURIComponent(promptId)}`
    const body = await this.getJson(path, signal)
    if (typeof body !== 'object' || body === null) {
      throw new ComfyProtocolError(`${this.config.endpoint}${path}`, 'the body is not an object')
    }
    return body as ComfyHistory
  }

  /* --------------------------------------------------------------- telemetry */

  /**
   * Start the telemetry socket and keep it up until the lifetime signal fires.
   *
   * Idempotent — a second call while the pump is running does nothing. Returns immediately;
   * the pump runs until teardown, until reconnection is exhausted, or immediately if this
   * interpreter has no global `WebSocket` (see {@link pump}'s pre-flight).
   *
   * The `.catch()` is not decorative. `plugin.ts` calls this from the startup path, so an
   * unhandled rejection here would be an unhandled rejection at plugin load — which node has
   * terminated the process for since v15. A telemetry socket failing must never take the
   * harness down with it; the REST half is independent and stays usable.
   */
  connect(): void {
    if (this.pumping) return
    this.pumping = true
    void this.pump().catch((error: unknown) => {
      this.pumping = false
      this.ctx.logger.error(`comfyui: telemetry pump stopped unexpectedly: ${renderThrown(error)}`)
    })
  }

  /**
   * The socket URL, including the session id when one is known.
   *
   * Blueprint: `references/ComfyUI/server.py:269-278`. `clientId` is a query parameter; absent,
   * the server mints `uuid.uuid4().hex`. Reusing a value **evicts** the socket that held it —
   * `self.sockets.pop(sid, None)` at `:276`. That is what makes reconnecting under the same id
   * safe (the dead socket is replaced, not duplicated), and it is also why two bridges
   * configured with the same `clientId` will silently disconnect each other in a loop.
   */
  private socketUrl(): string {
    const base = `${this.config.wsEndpoint}/ws`
    return this.sessionId === undefined ? base : `${base}?clientId=${encodeURIComponent(this.sessionId)}`
  }

  /**
   * Reconnect loop. Each iteration owns one socket from open to close.
   *
   * The pre-flight is load-bearing and is not a stylistic guard. `requireWebSocket()` is called
   * inside {@link runSocket}, which is inside this loop's `try` — so on an interpreter with no
   * global `WebSocket` (this box: node v20.19.2, measured) the missing-global error would be
   * caught as though it were a closed socket and fed into the retry ladder: ten attempts,
   * backoff to 15 s, ten `comfyui/disconnected` emissions, ~2.5 minutes of a machine retrying a
   * condition that cannot change. A missing global is not a transient network fault. It is
   * checked once, reported once, and the pump returns without ever starting — the REST half of
   * this client is unaffected and keeps working, which is the correct degradation.
   */
  private async pump(): Promise<void> {
    try {
      requireWebSocket()
    } catch (error) {
      this.ctx.logger.error(
        `comfyui: telemetry socket not started. ${renderThrown(error)} ` +
          'REST calls are unaffected; live progress is unavailable and run outcomes must be ' +
          'read from GET /history.',
      )
      this.pumping = false
      return
    }

    let attempt = 0
    while (!this.lifetime.aborted) {
      let reason: string
      try {
        reason = await this.runSocket()
        attempt = 0
      } catch (error) {
        reason = renderThrown(error)
      }

      if (this.lifetime.aborted) break

      attempt += 1
      const retrying = attempt <= RECONNECT_MAX_ATTEMPTS
      // Announced, never papered over: frames sent while the socket was down are gone, and
      // `GET /history/{prompt_id}` is the durable record. Nothing is synthesised to fill it.
      this.ctx.emit('comfyui/disconnected', { reason, attempt, retrying })
      if (!retrying) {
        this.ctx.logger.error(
          `comfyui: telemetry socket gave up after ${RECONNECT_MAX_ATTEMPTS} attempts (${reason}). ` +
            'Run outcomes are still readable from /history; live progress is not.',
        )
        break
      }
      const backoff = Math.min(RECONNECT_MAX_MS, RECONNECT_BASE_MS * 2 ** (attempt - 1))
      this.ctx.logger.warn(`comfyui: telemetry socket closed (${reason}); retry ${attempt} in ${backoff} ms`)
      await delay(backoff, this.lifetime)
    }
    this.pumping = false
  }

  /**
   * Open one socket and pump it until it closes. Resolves with the close reason.
   *
   * Rejects only if the constructor itself throws — a failed *connection* arrives as a close
   * event, not as a rejection, so the caller treats both the same way.
   *
   * Blueprint for the listener shape:
   * `references/deepseek-harness/packages/client/connection/src/client/web-api-client.ts:34-80`
   * — `addEventListener` throughout, abort wired with `{once: true}` and then re-checked
   * synchronously in case the signal already fired, and **malformed frames logged and dropped
   * rather than thrown**. That last one is deliberate there and copied deliberately here: one
   * unparseable frame must not take down a socket carrying a running job's progress.
   *
   * It diverges from that reference in one way, on purpose. `web-api-client` is an async
   * generator draining one request's stream; this socket is long-lived and fans out to the
   * Cordis bus, so there is no consumer to pull frames and the inbox/wake machinery it needs
   * has no counterpart here.
   */
  private runSocket(): Promise<string> {
    const WebSocketCtor = requireWebSocket()
    const url = this.socketUrl()
    const socket = new WebSocketCtor(url)
    // Without this the payload arrives as a Blob in some runtimes and the 4-byte big-endian
    // prefix read in `handleBinary` fails at runtime rather than at compile time.
    socket.binaryType = 'arraybuffer'
    this.socket = socket

    return new Promise<string>(resolve => {
      let settled = false
      const finish = (reason: string): void => {
        if (settled) return
        settled = true
        this.lifetime.removeEventListener('abort', handleAbort)
        if (this.socket === socket) this.socket = undefined
        resolve(reason)
      }

      const handleAbort = (): void => {
        if (socket.readyState === WebSocketCtor.CONNECTING || socket.readyState === WebSocketCtor.OPEN) {
          socket.close(1000, 'comfyui: plugin unloaded')
        }
        finish('plugin unloaded')
      }

      socket.addEventListener('open', () => {
        this.ctx.logger.info(`comfyui: telemetry socket open at ${url}`)
      })

      socket.addEventListener('message', event => {
        this.handleFrame((event as MessageEvent<unknown>).data)
      })

      socket.addEventListener('error', () => {
        // Always followed by `close`, which is what resolves. Recorded so the close reason is
        // not the only evidence that something went wrong.
        this.ctx.logger.debug(`comfyui: telemetry socket error at ${url}`)
      })

      socket.addEventListener(
        'close',
        event => {
          const closeEvent = event as CloseEvent
          const detail = closeEvent.reason ? `${closeEvent.code} ${closeEvent.reason}` : String(closeEvent.code)
          finish(`closed (${detail})`)
        },
        { once: true },
      )

      this.lifetime.addEventListener('abort', handleAbort, { once: true })
      if (this.lifetime.aborted) handleAbort()
    })
  }

  /** Route one websocket message by its runtime type. */
  private handleFrame(data: unknown): void {
    if (typeof data === 'string') {
      this.handleText(data)
      return
    }
    if (data instanceof ArrayBuffer) {
      this.handleBinary(data)
      return
    }
    if (ArrayBuffer.isView(data)) {
      // Some runtimes hand back a view rather than the buffer even with binaryType set.
      const view = data as ArrayBufferView
      this.handleBinary(view.buffer.slice(view.byteOffset, view.byteOffset + view.byteLength) as ArrayBuffer)
      return
    }
    this.ctx.logger.warn(`comfyui: dropped a websocket frame of unexpected type ${typeof data}`)
  }

  /**
   * Decode a text frame and put it on the bus **unchanged**.
   *
   * The honesty rule from `types.ts` reaching its enforcement point: nothing here rounds a
   * progress value, converts a step count into a percentage or synthesises a completion. The
   * only thing read out of a frame on the way past is `sid`, and that is read, not rewritten.
   */
  private handleText(text: string): void {
    let parsed: unknown
    try {
      parsed = JSON.parse(text)
    } catch (error) {
      this.ctx.logger.warn(`comfyui: dropped an unparseable telemetry frame (${renderThrown(error)})`)
      return
    }
    if (!isTelemetryFrame(parsed)) {
      this.ctx.logger.warn('comfyui: dropped a telemetry frame with no `type` field')
      return
    }
    if (parsed.type === 'status') this.captureSessionId(parsed.data)
    this.ctx.emit('comfyui/telemetry', parsed)
    this.settleWaiters(parsed)
  }

  /**
   * Decode the 4-byte big-endian event id and forward the rest untouched.
   *
   * Blueprint: `references/ComfyUI/server.py:1302-1310` (`encode_bytes`) and
   * `references/ComfyUI/protocol.py`. The payload's own inner header varies by id and is
   * documented on {@link ComfyBinaryFrame}; it is not parsed here, because decoding an image
   * would be this layer touching data it exists to relay.
   */
  private handleBinary(buffer: ArrayBuffer): void {
    if (buffer.byteLength < 4) {
      this.ctx.logger.warn(`comfyui: dropped a binary frame of ${buffer.byteLength} bytes — too short for an event id`)
      return
    }
    const event = new DataView(buffer).getUint32(0, false) as ComfyBinaryEventId
    const frame: ComfyBinaryFrame = { event, payload: new Uint8Array(buffer, 4) }
    this.ctx.logger.debug(`comfyui: binary frame ${binaryEventName(event)}, ${frame.payload.byteLength} bytes`)
    this.ctx.emit('comfyui/binary', frame)
  }

  /** Learn the session id from the connect frame. See {@link sessionId} for why this matters. */
  private captureSessionId(data: unknown): void {
    if (typeof data !== 'object' || data === null) return
    const sid = (data as { sid?: unknown }).sid
    if (typeof sid !== 'string' || sid.length === 0) return
    if (this.sessionId === sid) return
    const previous = this.sessionId
    this.sessionId = ClientId(sid)
    if (previous === undefined) {
      this.ctx.logger.info(`comfyui: session id ${sid} (server-minted; reused on every reconnect)`)
    } else {
      // Reaching here means the server did not honour the id sent on the query string, so any
      // prompt already queued under `previous` is now addressed to a session nobody holds.
      this.ctx.logger.warn(
        `comfyui: session id changed ${previous} -> ${sid}. Telemetry for prompts queued under ` +
          'the old id will not arrive; read /history/{prompt_id} for their outcomes.',
      )
    }
  }

  /* ----------------------------------------------------------------- waiting */

  /**
   * Resolve when a queued prompt finishes, with a three-valued verdict.
   *
   * The socket is the fast path: `execution_success` and `execution_error` both carry
   * `prompt_id`, so correlation needs nothing invented. But **the socket is not a reliable
   * witness** — if it drops across the completion, the frame is simply gone. An unbounded wait
   * on a frame that will never arrive is worse than no method at all, so this is bounded by
   * `timeoutMs` and falls back to `GET /history/{prompt_id}`, which is the durable record.
   *
   * It never rejects for a run that failed: a failed run is an `error` outcome, and a run whose
   * fate cannot be established is `unconfirmed`. Only a broken *call* throws. See
   * {@link ComfyPromptOutcome} for why the third value exists rather than being folded into one
   * of the other two.
   */
  async waitForPrompt(promptId: string, options: WaitForPromptOptions = {}): Promise<ComfyPromptOutcome> {
    const budget = options.timeoutMs ?? this.config.timeoutMs

    const settled = await new Promise<ComfyPromptOutcome | undefined>(resolve => {
      let done = false
      const waiter: PromptWaiter = { promptId, settle: outcome => finish(outcome) }
      const finish = (outcome: ComfyPromptOutcome | undefined): void => {
        if (done) return
        done = true
        clearTimeout(timer)
        this.waiters.delete(waiter)
        options.signal?.removeEventListener('abort', handleAbort)
        this.lifetime.removeEventListener('abort', handleAbort)
        resolve(outcome)
      }
      const handleAbort = (): void => finish(undefined)
      const timer = setTimeout(() => finish(undefined), budget)

      this.waiters.add(waiter)
      options.signal?.addEventListener('abort', handleAbort, { once: true })
      this.lifetime.addEventListener('abort', handleAbort, { once: true })
      if (options.signal?.aborted === true || this.lifetime.aborted) handleAbort()
    })

    if (settled !== undefined) return settled
    return await this.outcomeFromHistory(promptId, `no completion frame within ${budget} ms`)
  }

  /** Settle any waiter whose prompt just finished. Called from {@link handleText}. */
  private settleWaiters(frame: ComfyTelemetryFrame): void {
    if (frame.type !== 'execution_success' && frame.type !== 'execution_error') return
    const id = readPromptId(frame.data)
    if (id === undefined) return
    const outcome: ComfyPromptOutcome['outcome'] = frame.type === 'execution_success' ? 'success' : 'error'
    for (const waiter of [...this.waiters]) {
      if (waiter.promptId !== id) continue
      this.waiters.delete(waiter)
      waiter.settle({ promptId: PromptId(id), outcome, source: 'socket', frame })
    }
  }

  /**
   * Read a run's fate from history when the socket could not supply it.
   *
   * Every branch that cannot establish an outcome returns `unconfirmed` with the reason in
   * words rather than guessing. Notably, **no record at all is not a failure**: an unknown
   * prompt id answers `{}` with a 200 (`execution.py:1388`), and a prompt that is still queued
   * has no history entry yet, so absence means "not finished or not known", never "errored".
   */
  private async outcomeFromHistory(promptId: string, reason: string): Promise<ComfyPromptOutcome> {
    const id = PromptId(promptId)
    let history: ComfyHistory
    try {
      history = await this.historyFor(promptId)
    } catch (error) {
      return {
        promptId: id,
        outcome: 'unconfirmed',
        source: 'unavailable',
        reason: `${reason}; history could not be read (${renderThrown(error)})`,
      }
    }

    const record = history[promptId]
    if (record === undefined) {
      return {
        promptId: id,
        outcome: 'unconfirmed',
        source: 'history',
        reason: `${reason}; no history record — the prompt may still be queued or running`,
      }
    }
    const status = record.status
    if (status === undefined || status === null) {
      return {
        promptId: id,
        outcome: 'unconfirmed',
        source: 'history',
        record,
        reason: `${reason}; the history record carries no status`,
      }
    }
    return {
      promptId: id,
      outcome: status.status_str === 'success' ? 'success' : 'error',
      source: 'history',
      record,
    }
  }
}
