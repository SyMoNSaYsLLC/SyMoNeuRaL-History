/**
 * Configuration, wire types and event signatures for the ComfyUI bridge plugin.
 *
 * Everything in this file is a transcription of something that exists in a reference tree on
 * this box. Nothing is inferred from general knowledge of either project, and the negative
 * constraint that produced that rule caught two real mistakes while this file was written —
 * both recorded in `plugin.ts`, because both are about the plugin lifecycle rather than about
 * these types.
 *
 * The two sources, and what each one is authoritative for:
 *
 *   references/deepseek-harness/   the plugin shape: `name` / `inject` / `Config` / `apply`,
 *                                  the schema builder, and how a plugin augments `Context`
 *                                  and `Events`.
 *   references/ComfyUI/            the wire: every route path, every request field, every
 *                                  response field and every websocket message type below was
 *                                  read out of `server.py`, `execution.py` and
 *                                  `comfy_execution/progress.py` at the line cited beside it.
 *
 * ## This file takes a runtime dependency, and #89 says not to
 *
 * Read the two lines below this comment before believing anything about compliance. They are
 * `import` statements against `@deepseek-ai/cordis` and `@deepseek-ai/schemastery`, and both
 * bring in *runtime values* — `Service` is extended, `z` is called. `PROJECT-TASKS.md` #89 says
 * "read for behaviour, nothing imported, linked or served, and what ships is ours", and
 * `import` is the first word on that list. **This plugin does not satisfy #89 and this comment
 * will not pretend it does.**
 *
 * It is written this way deliberately, on a more specific instruction: Garrett named
 * `apply(ctx: Context, config)`, the service attached at `ctx.comfyui`, and "the schema system
 * from /references/DeepSeek Harness". A plugin that mounts on a Cordis context cannot be
 * written without Cordis — that is what mounting means. So the consequence is stated plainly
 * rather than hidden: **this package only runs inside a DeepSeek Harness install**, and
 * adopting it is a dependency decision for the whole repo, not a reference reading.
 *
 * What *is* true of #89: no file from either tree is copied, vendored or served. The ComfyUI
 * side is transcribed interface only. Licences were read rather than assumed — the harness root,
 * `vendor/cordis` and `vendor/schemastery` are all MIT (`references/deepseek-harness/LICENSE`,
 * and the `"license"` field of each vendored `package.json`), so the dependency is permitted;
 * whether it is wanted is Garrett's call and is not made here.
 *
 * @module @symoneural/plugin-comfyui
 */

import z from '@deepseek-ai/schemastery'

/* ------------------------------------------------------------------ identity */

/*
 * Three ids travel through this plugin and two of them are UUID-shaped strings that mean
 * completely different things. Branding them costs nothing at runtime and makes passing a
 * client id where a prompt id belongs a compile error rather than a queue that silently
 * never reports.
 */

/** A queued execution, minted by the server or supplied by us. See {@link ComfyPromptRequest}. */
export type PromptId = string & { readonly __brand: 'ComfyPromptId' }

/** A node's key within a graph object — the string key of a {@link ComfyGraph} entry. */
export type NodeId = string & { readonly __brand: 'ComfyNodeId' }

/**
 * A websocket session identifier.
 *
 * Blueprint: `references/ComfyUI/server.py:273` — `sid = request.rel_url.query.get('clientId', '')`.
 * Supplying one reconnects to an existing session and *evicts the previous socket* for that
 * id (`self.sockets.pop(sid, None)`, line 276); omitting it makes the server mint
 * `uuid.uuid4().hex`. Two agents sharing a client id therefore silently disconnect each
 * other, which is why `clientId` is per-instance config and not a constant.
 */
export type ClientId = string & { readonly __brand: 'ComfyClientId' }

/**
 * Brand a string as a {@link PromptId}.
 *
 * Blueprint: `references/deepseek-harness/packages/workspace/workspace/src/index.ts:36` —
 * `export function WorkspaceId(id: string): WorkspaceId { return id as WorkspaceId }`.
 *
 * @param id - Raw prompt id, as returned by `POST /prompt`.
 * @returns the same string, branded at compile time.
 */
export function PromptId(id: string): PromptId {
  return id as PromptId
}

/**
 * Brand a string as a {@link NodeId}.
 *
 * @param id - Raw node key from a ComfyUI graph object.
 * @returns the same string, branded at compile time.
 */
export function NodeId(id: string): NodeId {
  return id as NodeId
}

/**
 * Brand a string as a {@link ClientId}.
 *
 * @param id - Raw client id used for `/ws?clientId=` and `/prompt`'s `client_id`.
 * @returns the same string, branded at compile time.
 */
export function ClientId(id: string): ClientId {
  return id as ClientId
}

/* ------------------------------------------------------------------ config */

/**
 * Plugin config.
 *
 * Blueprint: `references/deepseek-harness/packages/bundle/headless/src/index.ts:30-38` — an
 * exported `interface Config` documenting each field, paired with an exported
 * `const Config: z<Config>` of the same name.
 */
export interface ComfyPluginConfig {
  /** Base URL of the ComfyUI REST API, with no trailing slash. */
  endpoint: string
  /**
   * Base URL for the telemetry socket. Empty means "derive it from {@link endpoint}", which
   * is what the plugin does, because on this box the two are always the same origin.
   */
  wsEndpoint: string
  /**
   * Websocket session id for queue isolation. Empty means "let the server mint one".
   * @see ClientId — two instances sharing a value evict each other's socket.
   */
  clientId: string
  /** Network and execution timeout, in milliseconds. */
  timeoutMs: number
  /** Restore the last known-good graph when an execution reports a graph fault. */
  autoRollback: boolean
}

/**
 * Config schema and defaults.
 *
 * The default endpoint is `http://127.0.0.1:8188`, which is not a guess either: it is the
 * address `scripts/comfyui.sh` binds in this repository, and the loopback-only binding is the
 * reason no credential appears anywhere in this config. If this ever needs to reach a remote
 * ComfyUI, the transport question and the authentication question arrive together and neither
 * should be answered by quietly widening a default.
 *
 * Blueprint: `references/deepseek-harness/packages/bundle/headless/src/index.ts:36` —
 * `export const Config: z<Config> = z.object({ ... })`.
 * Builder surface — `.default()`, `.description()`, `.required()`, `.min()`, `.max()` — read
 * from `references/deepseek-harness/vendor/schemastery/src/index.ts:157-171`.
 */
export const ComfyPluginConfig: z<ComfyPluginConfig> = z.object({
  endpoint: z.string()
    .default('http://127.0.0.1:8188')
    .description('Base URL of the ComfyUI REST API. No trailing slash; loopback by default.'),
  wsEndpoint: z.string()
    .default('')
    .description('Telemetry websocket base URL. Empty derives it from the endpoint.'),
  clientId: z.string()
    .default('')
    .description('Websocket session id for queue isolation. Empty lets the server mint one.'),
  timeoutMs: z.number()
    .min(1)
    .default(60_000)
    .description('Network and execution timeout in milliseconds.'),
  autoRollback: z.boolean()
    .default(true)
    .description('Restore the last known-good graph when an execution reports a graph fault.'),
})

/**
 * Config after {@link ComfyPluginConfig} has been applied and the two "empty means derive it"
 * fields have been resolved. The service holds this, never the raw form, so no code below the
 * entrypoint has to re-answer a question the entrypoint already answered.
 */
export interface ResolvedComfyConfig {
  /** {@link ComfyPluginConfig.endpoint}, trailing slashes removed. */
  readonly endpoint: string
  /** Telemetry socket origin, always populated: `ws://` or `wss://`, no trailing slash. */
  readonly wsEndpoint: string
  /** Client id, or `undefined` to let the server mint one on connect. */
  readonly clientId: ClientId | undefined
  /** {@link ComfyPluginConfig.timeoutMs}. */
  readonly timeoutMs: number
  /** {@link ComfyPluginConfig.autoRollback}. */
  readonly autoRollback: boolean
}

/* ------------------------------------------------------------------ graph */

/**
 * One node in a ComfyUI prompt graph.
 *
 * Blueprint: `references/ComfyUI/server.py:1112` — the object posted as `prompt` is passed
 * straight to `execution.validate_prompt(prompt_id, prompt, partial_execution_targets)`, so
 * this is the API-format graph (node id → node), not the editor's `workflow` format. The two
 * are different documents and only this one is accepted by `/prompt`.
 */
export interface ComfyNode {
  /** Registered node class, as keyed in `/object_info`. */
  class_type: string
  /**
   * Input slots. A literal is a value; a `[nodeId, outputIndex]` pair is a link from another
   * node's output.
   */
  inputs: Record<string, ComfyInputValue>
  /** Editor-supplied display metadata. Carried through untouched. */
  _meta?: { title?: string }
}

/** A node input: a literal, or a `[sourceNodeId, outputIndex]` link. */
export type ComfyInputValue = string | number | boolean | null | [string, number]

/** An API-format prompt graph: node id → node. */
export type ComfyGraph = Record<string, ComfyNode>

/* ------------------------------------------------------------------ REST wire */

/**
 * Body of `POST /prompt`.
 *
 * Blueprint: `references/ComfyUI/server.py:1072-1140`. Every optional field below is optional
 * *there*, and the two that look interchangeable are not:
 *
 * - `prompt_id` absent or explicitly null makes the server mint one; a supplied value must be
 *   canonical lowercase hyphenated UUID or the call is refused with 400 `invalid_prompt_id`
 *   (line 1090-1104).
 * - `client_id` is copied into `extra_data` (line 1117-1118) and is what routes telemetry back to
 *   one socket. It is not the prompt id and does not have to be a UUID.
 *
 * `number` and `front` are alternatives, not companions: `number` is read directly when
 * present, and `front` is only consulted in the branch where it is absent (line 1078-1086).
 */
export interface ComfyPromptRequest {
  /** The API-format graph to execute. */
  prompt: ComfyGraph
  /** Caller-chosen prompt id. Omit to have the server mint one. */
  prompt_id?: PromptId
  /** Routes telemetry to one websocket session. */
  client_id?: ClientId
  /** Free-form execution metadata. `client_id` is merged in here by the server. */
  extra_data?: Record<string, unknown>
  /** Explicit queue priority. Mutually exclusive with `front`. */
  number?: number
  /** Queue at the front. Only consulted when `number` is absent. */
  front?: boolean
  /** Execute only the subgraph feeding these nodes. */
  partial_execution_targets?: string[]
}

/**
 * Success response of `POST /prompt`.
 *
 * Blueprint: `references/ComfyUI/server.py:1132` —
 * `{"prompt_id": prompt_id, "number": number, "node_errors": valid[3]}`.
 *
 * Note `node_errors` on the *success* path. A prompt can be accepted and still carry per-node
 * complaints, so an empty-object check on this field is a real assertion and not a formality.
 */
export interface ComfyPromptResponse {
  /** Id to correlate every subsequent telemetry frame and history lookup. */
  prompt_id: PromptId
  /** Queue position assigned by the server. */
  number: number
  /** Per-node complaints raised during validation of an otherwise accepted prompt. */
  node_errors: Record<string, unknown>
}

/**
 * Error body returned with 400 by `POST /prompt`.
 *
 * Blueprint: `references/ComfyUI/server.py:1098-1104` (invalid prompt id),
 * `:1135-1136` (invalid prompt) and `:1138-1144` (no prompt). All three share this shape.
 */
export interface ComfyPromptError {
  error: {
    /** Machine-readable tag, e.g. `invalid_prompt_id`, `no_prompt`. */
    type: string
    /** One-line summary. */
    message: string
    /** Longer explanation, sometimes naming the fix. */
    details: string
    /** Additional context; frequently empty. */
    extra_info: Record<string, unknown>
  }
  /** Per-node validation failures. */
  node_errors: Record<string, unknown>
}

/**
 * Response of `GET /system_stats`.
 *
 * Blueprint: `references/ComfyUI/server.py:686`. This is the discovery probe: it is a cheap
 * GET that exists on every build, needs no graph and queues nothing, which is what makes it
 * safe to call at plugin start. Only the fields this plugin reads are typed; the endpoint
 * returns more.
 */
export interface ComfySystemStats {
  system: {
    os: string
    comfyui_version?: string
    python_version: string
    pytorch_version?: string
    [key: string]: unknown
  }
  devices: Array<{
    name: string
    type: string
    vram_total: number
    vram_free: number
    [key: string]: unknown
  }>
}

/**
 * Response of `GET /queue`.
 *
 * Blueprint: `references/ComfyUI/server.py:1064-1070` — `queue_running` and `queue_pending`,
 * each passed through `_remove_sensitive_from_queue` before it is serialised.
 */
export interface ComfyQueueState {
  queue_running: unknown[]
  queue_pending: unknown[]
}

/* ------------------------------------------------------------------ telemetry */

/**
 * Every websocket message type ComfyUI emits, enumerated from the reference tree rather than
 * recalled.
 *
 * **The method matters and an earlier revision of this comment stated it wrong.** It said the
 * set was taken by grepping every `send_sync("...")` and `add_message("...")` call site. Those
 * are two of the three emitting forms; the third is a direct `await self.send("...", ...)`, and
 * missing it cost exactly one type — `feature_flags` at `references/ComfyUI/server.py:308`,
 * which no grep of the other two forms could ever have found. The list below was rebuilt over
 * all three forms. Five of the eleven are emitted from `execution.py` and
 * `comfy_execution/progress.py` rather than from `server.py`, so reading the server alone would
 * have produced a plausible, incomplete union in the other direction too.
 *
 * The correction is left visible rather than quietly patched because the sentence describing the
 * method is the only record of how the list was built, and a rigor claim with a known hole in it
 * is worse than no claim — the next reader trusts it and stops checking.
 *
 * | type                | emitted at                                        |
 * |---------------------|---------------------------------------------------|
 * | `status`            | `server.py:287` (on connect) and `:1287`          |
 * | `feature_flags`     | `server.py:308` — reply to the client's first frame |
 * | `execution_start`   | `execution.py:742`                                |
 * | `execution_cached`  | `execution.py:770`                                |
 * | `executing`         | `server.py:289` (on reconnect) and execution      |
 * | `progress`          | `comfy_execution/progress.py:224`                 |
 * | `progress_state`    | `comfy_execution/progress.py:183`                 |
 * | `executed`          | execution                                         |
 * | `execution_success` | `execution.py:824`                                |
 * | `execution_error`   | execution                                         |
 * | `logs`              | server                                            |
 */
export type ComfyTelemetryType =
  | 'status'
  | 'feature_flags'
  | 'execution_start'
  | 'execution_cached'
  | 'executing'
  | 'progress'
  | 'progress_state'
  | 'executed'
  | 'execution_success'
  | 'execution_error'
  | 'logs'

/**
 * A decoded text frame from `/ws`.
 *
 * Blueprint: `references/ComfyUI/server.py:287` — `await self.send("status", {...}, sid)`, a
 * `{type, data}` envelope. Binary frames (preview images) are not text frames and are not
 * this type.
 *
 * `data` is deliberately `unknown` at the envelope level and narrowed by the members below.
 * A frame whose `type` is outside {@link ComfyTelemetryType} is still a valid envelope: the
 * upstream project adds message types, and a bridge that throws on an unrecognised one would
 * break on a ComfyUI upgrade that changed nothing this plugin uses.
 */
export interface ComfyTelemetryFrame {
  type: ComfyTelemetryType | (string & {})
  data: unknown
}

/**
 * `status` — queue depth, plus the session id on the first frame after connect.
 *
 * Blueprint: `references/ComfyUI/server.py:287` and `:1283-1287`. `sid` is present only on
 * the connect frame, and it is the only place a server-minted client id is ever disclosed.
 */
export interface ComfyStatusData {
  status: { exec_info: { queue_remaining: number } }
  sid?: string
}

/**
 * `feature_flags` — the server's half of a capability negotiation.
 *
 * Blueprint: `references/ComfyUI/server.py:302-312`. The server sends this **only** in reply to
 * a client that made `{"type":"feature_flags","data":{…}}` its *first* text frame; the handler
 * stores the client's flags in `sockets_metadata[sid]["feature_flags"]` and answers with
 * `feature_flags.get_server_features()` (`comfy_api/feature_flags.py:159-166`, which returns a
 * copy of `SERVER_FEATURE_FLAGS`).
 *
 * Two consequences for anything driving this socket. The first text frame is a **negotiation
 * slot**: send anything else and the slot is spent, because the handler only inspects the first
 * message. And a client that never negotiates simply gets no `feature_flags` frame — which is
 * the state this plugin is in deliberately, since it has not identified a feature it needs to
 * ask for. The member exists so a frame arriving from a client that *did* negotiate is a known
 * type rather than an unrecognised one.
 *
 * The contents are the server's to define and are not enumerated here; reading them as
 * `Record<string, unknown>` is the honest shape for a payload this plugin does not interpret.
 */
export interface ComfyFeatureFlagsData {
  [flag: string]: unknown
}

/** `execution_start` — the queued prompt has begun. Blueprint: `execution.py:742`. */
export interface ComfyExecutionStartData {
  prompt_id: string
}

/**
 * `execution_cached` — these nodes were satisfied from cache and will not run.
 * Blueprint: `references/ComfyUI/execution.py:770`.
 */
export interface ComfyExecutionCachedData {
  prompt_id: string
  nodes: string[]
}

/**
 * `executing` — the currently running node, or `null` at end of run.
 *
 * Blueprint: `references/ComfyUI/server.py:289` — `await self.send("executing", {"node":
 * self.last_node_id}, sid)` on reconnect, which is also the shape emitted during a run.
 */
export interface ComfyExecutingData {
  node: string | null
  prompt_id?: string
}

/** `progress` — step counter within one node. Blueprint: `comfy_execution/progress.py:224`. */
export interface ComfyProgressData {
  value: number
  max: number
  prompt_id?: string
  node?: string | null
}

/**
 * `progress_state` — per-node progress for the whole graph in one frame.
 * Blueprint: `references/ComfyUI/comfy_execution/progress.py:183-184` —
 * `{"prompt_id": prompt_id, "nodes": active_nodes}`.
 */
export interface ComfyProgressStateData {
  prompt_id: string
  nodes: Record<string, { value: number; max: number; state?: string; node_id?: string }>
}

/** `executed` — one node produced output. */
export interface ComfyExecutedData {
  node: string
  prompt_id: string
  output: Record<string, unknown>
}

/** `execution_success` — the whole prompt completed. Blueprint: `execution.py:824`. */
export interface ComfyExecutionSuccessData {
  prompt_id: string
}

/**
 * `execution_error` — the run failed. This is the frame `autoRollback` reacts to, and the
 * reason the flag is worth having: by the time it arrives the graph on the server is the
 * mutated one, so "put it back" needs a copy taken before the mutation.
 */
export interface ComfyExecutionErrorData {
  prompt_id: string
  node_id?: string
  node_type?: string
  exception_message?: string
  exception_type?: string
  traceback?: string[]
  [key: string]: unknown
}

/* ------------------------------------------------------------------ history */

/**
 * The verdict a finished run leaves behind.
 *
 * Blueprint: `references/ComfyUI/execution.py:1281-1284` — a `NamedTuple` with exactly these
 * three fields, deep-copied to a dict at `:1293` and stored under `status`.
 */
export interface ComfyExecutionStatus {
  status_str: 'success' | 'error'
  completed: boolean
  messages: unknown[]
}

/**
 * One history entry.
 *
 * Blueprint: `references/ComfyUI/execution.py:1300-1305` — the record is built as
 * `{"prompt": …, "outputs": {}, "status": status_dict}` and then `.update(history_result)`
 * merges the run's real outputs over the top, so the field set is open and the index signature
 * is not laziness.
 *
 * **`status` is genuinely nullable.** `task_done` sets `status_dict = None` when it is handed no
 * status (`:1292-1294`), so a record can exist with no verdict on it. Anything reading this to
 * decide whether a run succeeded needs a third answer for that case — see
 * {@link ComfyPromptOutcome}, and `desktop-client/README.md`'s three-valued `check.passed`,
 * which is the same rule already applied elsewhere in this repository: a gap where a verdict
 * belongs reads as "fine", so it has to be rendered as *unconfirmed* rather than as blank.
 */
export interface ComfyHistoryRecord {
  prompt?: unknown
  outputs?: Record<string, unknown>
  status?: ComfyExecutionStatus | null
  [key: string]: unknown
}

/**
 * The `GET /history` and `GET /history/{prompt_id}` document: prompt id → record.
 *
 * Blueprint: `references/ComfyUI/server.py:1045` and `:1059`, over
 * `execution.py:1364-1389`. Note the single-prompt form still returns a **map**, and an unknown
 * prompt id yields `{}` with a **200** (`:1388`) — not a 404. A caller that treats "not found"
 * as an HTTP error will never see it.
 */
export type ComfyHistory = Record<string, ComfyHistoryRecord>

/**
 * What a client concluded about one run, and how it concluded it.
 *
 * The `outcome` is deliberately three-valued. A run can finish, fail, or leave no readable
 * verdict at all — the socket dropped across the completion, or the history record carries a
 * null `status` (see {@link ComfyHistoryRecord}). Collapsing that third case into `error`
 * would report a failure that may not have happened, and collapsing it into `success` is
 * worse. `unconfirmed` says what is actually known.
 *
 * `source` is carried alongside because the two are not equally strong evidence and a caller
 * should be able to tell them apart: `socket` is the engine's own completion frame, `history`
 * is a durable record read afterwards, and `unavailable` means neither could be obtained.
 */
export interface ComfyPromptOutcome {
  promptId: PromptId
  outcome: 'success' | 'error' | 'unconfirmed'
  source: 'socket' | 'history' | 'unavailable'
  /** The `execution_success` / `execution_error` frame, when the socket delivered one. */
  frame?: ComfyTelemetryFrame
  /** The history record, when that is what settled it. */
  record?: ComfyHistoryRecord
  /** Why the outcome is `unconfirmed`, in words. Absent when it is not. */
  reason?: string
}

/* ------------------------------------------------------------- binary frames */

/**
 * The four binary event ids, read from `references/ComfyUI/protocol.py`.
 *
 * Every binary websocket frame is a 4-byte **big-endian** event id followed by a payload —
 * `encode_bytes` at `references/ComfyUI/server.py:1302-1310`, `struct.pack(">I", event)`. The
 * payload shape then depends on the id, and the three that reach the wire each carry a *second*
 * length- or type-prefixed header of their own. They are transcribed on {@link ComfyBinaryFrame}.
 *
 * `UNENCODED_PREVIEW_IMAGE` (2) is the one id that never appears on the wire. It is an internal
 * marker: `send()` at `server.py:1291` intercepts it, encodes the image, and emits it as
 * `PREVIEW_IMAGE` (1). A client that waits for a 2 waits forever.
 */
export const COMFY_BINARY_EVENT = {
  /** JPEG or PNG preview. Emitted at `server.py:1333`. */
  PREVIEW_IMAGE: 1,
  /** Internal marker only — see the note above. Never received. */
  UNENCODED_PREVIEW_IMAGE: 2,
  /** Per-node progress **text**, not an image. Emitted at `server.py:1479`. */
  TEXT: 3,
  /** Preview image with a JSON metadata header. Emitted at `server.py:1370`. */
  PREVIEW_IMAGE_WITH_METADATA: 4,
} as const

/** One of {@link COMFY_BINARY_EVENT}'s values, or any id a future ComfyUI adds. */
export type ComfyBinaryEventId = (typeof COMFY_BINARY_EVENT)[keyof typeof COMFY_BINARY_EVENT] | (number & {})

/**
 * A decoded binary websocket frame.
 *
 * **"Binary frame" does not mean "image".** `TEXT` (3) is a binary frame carrying UTF-8 progress
 * text for one node, and routing all four ids to a preview handler would render a node id and a
 * status string as a broken picture. Branch on {@link ComfyBinaryFrame.event}.
 *
 * The payload headers, each transcribed from its emit site:
 *
 * | id | payload |
 * |----|---------|
 * | 1 `PREVIEW_IMAGE` | 4-byte BE image type (`1` = JPEG, `2` = PNG — `server.py:1322-1328`), then the encoded image |
 * | 3 `TEXT` | 4-byte BE node-id byte length, then the node id, then the text — `server.py:1469-1479` |
 * | 4 `PREVIEW_IMAGE_WITH_METADATA` | 4-byte BE metadata JSON byte length, then the JSON, then the image — `server.py:1355-1370` |
 *
 * This plugin decodes the outer event id and hands the rest on as bytes. It does not parse the
 * inner headers, and it does not decode an image: the frames are forwarded so a consumer can,
 * and inventing a decode here would be this layer touching data it is supposed to relay.
 */
export interface ComfyBinaryFrame {
  /** The 4-byte big-endian prefix, decoded. */
  event: ComfyBinaryEventId
  /** Everything after the 4-byte prefix, untouched. */
  payload: Uint8Array
}

/* ------------------------------------------------------------- node metadata */

/**
 * One entry of `GET /object_info` — the definition of a single node class.
 *
 * Blueprint: `references/ComfyUI/server.py:800` (the whole map) and `:813`
 * (`/object_info/{node_class}`, the same value under a one-key object).
 *
 * Only the fields this plugin relies on are named. The rest is left to the index signature
 * rather than guessed at, because `input` in particular is a deeply irregular document — a
 * node's input spec is a tuple whose first element is either a type name or an array of
 * literal choices, and whose optional second element is a config object. Inventing a type for
 * it would be exactly the fabrication the build directive bars, and a consumer that needs it
 * should read the value rather than trust a shape asserted here.
 */
export interface ComfyNodeDefinition {
  name: string
  display_name?: string
  category?: string
  description?: string
  output_node?: boolean
  input?: { required?: Record<string, unknown>; optional?: Record<string, unknown>; hidden?: Record<string, unknown> }
  output?: unknown[]
  output_name?: string[]
  [key: string]: unknown
}

/** The `GET /object_info` document: node class name → definition. `server.py:800`. */
export type ComfyObjectInfo = Record<string, ComfyNodeDefinition>

/* ------------------------------------------------------------------ events */

/**
 * Events this plugin emits on the Harness bus.
 *
 * Blueprint: `references/deepseek-harness/packages/interaction/commands/src/types.ts:73` and
 * `packages/extensions/cordis-host-runner/src/types.ts:361` — a plugin augments `Events` from
 * a `declare module '@deepseek-ai/cordis'` block, one namespaced string key per event, each
 * documented with an explicit `@mode`.
 *
 * The namespace is `comfyui/`. Frames are re-emitted **unchanged**: nothing here rounds a
 * progress value, converts a step count into a percentage or synthesises a completion. That
 * is `.claude/CLAUDE.md`'s honesty rule reaching this file — a gauge downstream has to be
 * able to say it is showing what the engine reported, and it can only say that if this layer
 * did not touch it.
 */
declare module '@deepseek-ai/cordis' {
  interface Events {
    /**
     * The bridge reached the configured endpoint and read its stats. Carries the probe
     * result verbatim.
     * @param stats - the decoded `GET /system_stats` body.
     * @mode emit
     */
    'comfyui/connected'(stats: ComfySystemStats): void
    /**
     * The bridge could not reach the configured endpoint at start. Carries the typed
     * discovery failure; the plugin stays loaded and the service stays registered.
     * @param error - the discovery failure, with the endpoint that was tried.
     * @mode emit
     */
    'comfyui/unreachable'(error: Error): void
    /**
     * One decoded telemetry text frame, forwarded exactly as received.
     * @param frame - the `{type, data}` envelope from `/ws`.
     * @mode emit
     */
    'comfyui/telemetry'(frame: ComfyTelemetryFrame): void
    /**
     * One binary frame, with the 4-byte event id decoded and the payload untouched.
     *
     * Separate from `comfyui/telemetry` because it is a different document — see
     * {@link ComfyBinaryFrame}. It is emitted rather than dropped so that nothing the engine
     * sent disappears silently at this layer; a consumer that does not want previews simply
     * does not listen.
     * @param frame - the decoded binary frame.
     * @mode emit
     */
    'comfyui/binary'(frame: ComfyBinaryFrame): void
    /**
     * The telemetry socket closed and the client is about to retry, or has given up.
     *
     * **This is a gap marker, not a frame.** Frames that arrived while the socket was down are
     * gone and cannot be recovered from the socket; `GET /history/{prompt_id}` is the durable
     * record. Nothing is synthesised to fill the hole, because a fabricated progress value or
     * completion is precisely the dishonest reading `.claude/CLAUDE.md` bars — so the gap is
     * announced instead.
     * @param detail - why the socket dropped, and whether a retry is coming.
     * @mode emit
     */
    'comfyui/disconnected'(detail: { reason: string; attempt: number; retrying: boolean }): void
  }
}
