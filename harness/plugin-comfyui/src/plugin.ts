/**
 * ComfyUI bridge — plugin entrypoint and Cordis context lifecycle.
 *
 * Mounts one shared {@link ComfyBridge} service on the Harness context as `ctx.comfyui`,
 * resolves config, probes the configured endpoint once at startup, and tears its own effects
 * down when the fiber unloads. The REST and websocket transport is Deliverable 2 and is not
 * stubbed here: this file contains no placeholder method and nothing that returns a fabricated
 * value. What it does, it does for real.
 *
 * No file from `references/` is copied, vendored or served, and every convention below cites the
 * file it was read from. But this module **imports** `@deepseek-ai/cordis` and
 * `@deepseek-ai/schemastery` as runtime dependencies, so it does *not* meet
 * `PROJECT-TASKS.md` #89's "nothing imported" bar. See the header of `types.ts` for why that was
 * chosen and what it commits the repo to; the short version is that a plugin cannot mount on a
 * Cordis context without Cordis, and nothing here can build until that dependency is real.
 *
 * ## Two things the specification asked for that this codebase does not have
 *
 * Both were checked against the reference tree rather than assumed, and both are recorded here
 * because the correction is more useful than the code.
 *
 * 1. **There is no `ctx.on('ready')` and no `ctx.on('dispose')`.** The vendored Cordis declares
 *    its whole event surface in one interface — `references/deepseek-harness/vendor/cordis/src/events.ts:329`
 *    — and it holds exactly nine `internal/*` events. Neither `ready` nor `dispose` appears
 *    anywhere in `vendor/cordis/src/`. Writing those two listeners would have compiled against
 *    an augmented `Events` and then never fired.
 *
 *    The real conventions are two, and they are not interchangeable:
 *      - *startup* is `protected async [Service.init]()`, awaited by the fiber at
 *        `vendor/cordis/src/fiber.ts:257`. A service is not active until it resolves.
 *      - *teardown* is `ctx.effect(() => () => cleanup, 'label')`, as at
 *        `packages/hooks/hooks-claude-code/src/index.ts:126`. The effect body's return value
 *        is the disposer and the fiber runs it on unload.
 *
 * 2. **There is no `start()` / `stop()` pair on `Service`.** `vendor/cordis/src/service.ts`
 *    declares a constructor and five symbol-keyed hooks and no such methods; the fiber calls
 *    `[symbols.init]` and nothing else. `WorkspaceRegistry` at
 *    `packages/workspace/workspace/src/index.ts:126` is the shape to copy.
 *
 * @module @symoneural/plugin-comfyui
 */

import { Context, Service } from '@deepseek-ai/cordis'
import { ComfyClient, ComfyHttpError, ComfyProtocolError, ComfyTransportError } from './client.ts'
import * as ComfyTools from './tools.ts'
import {
  ClientId,
  ComfyPluginConfig,
  type ComfySystemStats,
  type ResolvedComfyConfig,
} from './types.ts'

/**
 * Plugin name.
 *
 * Blueprint: `references/deepseek-harness/packages/interaction/tool-ask-user/src/index.ts:13`
 * — `export const name = 'tool-ask-user'`, a bare kebab-case string, not a package specifier.
 */
export const name = 'comfyui-harness-bridge'

/**
 * Services required before this plugin activates.
 *
 * Empty, and deliberately so. `inject` is a *gate*: the fiber holds the plugin inactive until
 * every named service exists (`references/deepseek-harness/packages/interaction/tool-ask-user/src/index.ts:14`
 * injects `['tools', 'userQuestions']` because it registers a tool in `apply`).
 *
 * **This comment used to promise that deliverable 3 would add `'tools'` here. It does not, and
 * the reasoning that promise was based on was incomplete.** Tools now exist — `./tools.ts`
 * registers five — but they are registered by a *child* plugin mounted from `apply`, not by
 * this one. Putting `'tools'` on this gate would make the entire REST bridge unavailable on
 * any deployment with no tool registry, which is precisely the trade this comment already
 * argued against; the child fiber carries `inject: ['comfyui', 'tools']` instead, so only the
 * tool layer waits on the registry and the bridge stays usable without it.
 */
export const inject: string[] = []

/**
 * Config schema, re-exported under the name the loader reads.
 *
 * Blueprint: `references/deepseek-harness/packages/bundle/headless/src/index.ts:36` — the
 * loader looks for an exported `Config`, so the domain-named schema in `./types.ts` is
 * re-exported here rather than being defined twice.
 */
export const Config: typeof ComfyPluginConfig = ComfyPluginConfig

/**
 * Service augmentation.
 *
 * Blueprint: `references/deepseek-harness/packages/workspace/workspace/src/index.ts:66-70` —
 * a plugin declares its service on `Context` from its own module, so `ctx.comfyui` is typed
 * for any consumer that imports this package (or `import type {}` of it, for the side effect).
 */
declare module '@deepseek-ai/cordis' {
  interface Context {
    comfyui: ComfyBridge
  }
}

/* ------------------------------------------------------------------ errors */

/**
 * The configured endpoint did not answer at all: connection refused, DNS failure, TLS
 * failure, or the discovery probe exceeded `timeoutMs`.
 *
 * Distinct from {@link ComfyDiscoveryError} on purpose. This one means *nothing is listening
 * there*, which on this box is the ordinary state — `scripts/symoneural-ui.sh` starts ComfyUI on
 * demand and stops it again — and is not a fault. The other means something answered and was
 * not ComfyUI, which always is.
 *
 * Blueprint for the shape (a named subclass carrying the offending value as a readonly field,
 * with `this.name` set explicitly): `references/deepseek-harness/packages/workspace/workspace/src/index.ts:44-53`.
 */
export class ComfyUnreachableError extends Error {
  /**
   * The underlying failure is passed to `Error`'s own `cause` option rather than redeclared
   * as a field. Redeclaring it would need an `override` modifier under this tree's
   * `noImplicitOverride` (`references/deepseek-harness/tsconfig.base.json`) and would widen
   * `cause?: unknown` to a required property under `exactOptionalPropertyTypes` — two
   * compiler settings' worth of friction for a property the platform already provides.
   *
   * @param endpoint - The base URL that was tried.
   * @param cause - The underlying transport failure or timeout.
   */
  constructor(readonly endpoint: string, cause: unknown) {
    super(`comfyui unreachable at '${endpoint}': ${renderThrown(cause)}`, { cause })
    this.name = 'ComfyUnreachableError'
  }
}

/**
 * Something answered at the configured endpoint but did not answer as ComfyUI: a non-2xx
 * status, or a body that is not the documented `GET /system_stats` object.
 *
 * Worth separating from {@link ComfyUnreachableError} because the two have opposite fixes. An
 * unreachable endpoint is started; a wrong one is corrected. A single "could not connect" for
 * both sends whoever reads the log looking in the wrong place, and a proxy answering 404 on
 * every path is exactly the case that produces it.
 */
export class ComfyDiscoveryError extends Error {
  /**
   * @param endpoint - The base URL that was tried.
   * @param detail - What was wrong with the response.
   */
  constructor(readonly endpoint: string, readonly detail: string) {
    super(`comfyui at '${endpoint}' did not answer as ComfyUI: ${detail}`)
    this.name = 'ComfyDiscoveryError'
  }
}

/**
 * Render an unknown thrown value as one line.
 *
 * Blueprint: `renderThrown`, used throughout
 * `references/deepseek-harness/packages/schedule/schedule/src/runtime.ts:113`. `catch` binds
 * `unknown`, and a template literal on a non-Error yields `[object Object]`, so every log line
 * and every error message here goes through this.
 *
 * @param value - Any caught value.
 * @returns a single-line description.
 */
function renderThrown(value: unknown): string {
  if (value instanceof Error) return value.message
  return String(value)
}

/* ------------------------------------------------------------------ config */

/**
 * Resolve raw config into the form the service holds.
 *
 * Two fields are documented as "empty means derive it" and this is where that is answered,
 * once, so that nothing downstream has to re-answer it. Pure and total: it performs no I/O and
 * throws only on a config that could never work.
 *
 * The websocket origin is derived by swapping the scheme rather than by string-concatenating a
 * host, because `http`→`ws` and `https`→`wss` is the whole mapping and `new URL` is the only
 * thing that gets ports, IPv6 literals and trailing slashes right without a special case each.
 *
 * @param config - Raw config, after {@link Config} has applied its defaults.
 * @returns the resolved form.
 * @throws TypeError if `endpoint` is not a parsable absolute URL, or if its scheme is neither
 *   `http:` nor `https:` — there is no correct `ws` origin for any other scheme, and guessing
 *   one would defer the failure to the first connect, far from its cause.
 */
export function resolveConfig(config: ComfyPluginConfig): ResolvedComfyConfig {
  const endpoint = config.endpoint.replace(/\/+$/, '')
  let parsed: URL
  try {
    parsed = new URL(endpoint)
  } catch (error) {
    throw new TypeError(`comfyui: endpoint '${config.endpoint}' is not an absolute URL: ${renderThrown(error)}`)
  }
  if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') {
    throw new TypeError(`comfyui: endpoint '${config.endpoint}' must be http or https, not '${parsed.protocol}'`)
  }

  let wsEndpoint: string
  if (config.wsEndpoint) {
    wsEndpoint = config.wsEndpoint.replace(/\/+$/, '')
  } else {
    const derived = new URL(endpoint)
    derived.protocol = parsed.protocol === 'https:' ? 'wss:' : 'ws:'
    wsEndpoint = derived.toString().replace(/\/+$/, '')
  }

  return {
    endpoint,
    wsEndpoint,
    clientId: config.clientId ? ClientId(config.clientId) : undefined,
    timeoutMs: config.timeoutMs,
    autoRollback: config.autoRollback,
  }
}

/* ------------------------------------------------------------------ service */

/**
 * The shared ComfyUI bridge, mounted as `ctx.comfyui`.
 *
 * Holds the resolved config, the abort signal that bounds every request this plugin will ever
 * make, and the result of the one startup probe. Deliverable 2 attaches the REST and websocket
 * client to this same instance, which is why the lifetime lives here and not in the client:
 * there is one service per plugin activation, and disposing the fiber has to be enough to
 * stop every socket and every in-flight request without any of them being enumerated.
 *
 * Blueprint: `references/deepseek-harness/packages/workspace/workspace/src/index.ts:92-140` —
 * `extends Service`, `static inject`, a constructor that only calls `super(ctx, '<name>')`,
 * and all real startup in `[Service.init]`.
 */
export class ComfyBridge extends Service {
  /** Resolved config. Never the raw form; see {@link resolveConfig}. */
  readonly config: ResolvedComfyConfig

  /**
   * Aborted exactly once, when the owning fiber unloads.
   *
   * This is the connection-pool and socket cleanup the plugin owes, expressed as the one
   * mechanism that covers both. `fetch` takes it as `signal`, and so does the websocket
   * wrapper in Deliverable 2, so nothing has to keep a registry of live handles and nothing
   * can be missed by a teardown path that forgot to look somewhere.
   */
  private readonly lifetime = new AbortController()

  /**
   * The last successful probe, or `undefined` if the endpoint has never answered.
   *
   * Deliberately not a boolean. A boolean would say "connected" and a reader would believe it
   * long after the process at the far end had exited; this holds the reading itself, so a
   * consumer that shows it is showing a measurement and can say when it was taken.
   */
  stats: ComfySystemStats | undefined

  /**
   * The REST and telemetry client. Deliverable 2, `client.ts`.
   *
   * Public because it *is* the surface: `ctx.comfyui.http.queuePrompt(...)`. The bridge owns
   * discovery and lifetime; everything that talks to the engine lives on this.
   */
  readonly http: ComfyClient

  /**
   * @param ctx - The context to register in.
   * @param config - Resolved config, produced by {@link resolveConfig} in {@link apply}.
   */
  constructor(ctx: Context, config: ResolvedComfyConfig) {
    super(ctx, 'comfyui')
    this.config = config
    this.http = new ComfyClient(ctx, config, this.lifetime.signal)
  }

  /** An abort signal that fires when the plugin unloads. Pass it to every request. */
  get signal(): AbortSignal {
    return this.lifetime.signal
  }

  /**
   * Probe the endpoint once, and publish the outcome.
   *
   * Awaited by the fiber before the service becomes active
   * (`references/deepseek-harness/vendor/cordis/src/fiber.ts:257`), so a consumer that reads
   * `ctx.comfyui` has already had this run.
   *
   * **It does not throw when ComfyUI is down.** On this box ComfyUI is started on demand by
   * `scripts/symoneural-ui.sh` and stopped again, so absent is its normal state; rejecting here
   * would unload the plugin and take `ctx.comfyui` away exactly when a caller wants to ask
   * whether ComfyUI is up. Unreachable is reported on `comfyui/unreachable` and left as a
   * `stats` of `undefined`, which is a reading a consumer can render honestly. A
   * *misconfigured* endpoint is different and is logged as such, because nothing about it will
   * improve by waiting.
   */
  protected async [Service.init](): Promise<void> {
    this.ctx.effect(
      () => () => this.lifetime.abort(new Error('comfyui: plugin unloaded')),
      'comfyui.lifetime',
    )

    try {
      this.stats = await this.probe()
    } catch (error) {
      if (error instanceof ComfyDiscoveryError) {
        this.ctx.logger.warn(`comfyui: ${error.message}`)
      } else {
        this.ctx.logger.info(`comfyui: no engine at ${this.config.endpoint} (${renderThrown(error)})`)
      }
      this.ctx.emit('comfyui/unreachable', error instanceof Error ? error : new Error(renderThrown(error)))
      return
    }

    const device = this.stats.devices[0]
    this.ctx.logger.info(
      `comfyui: ${this.config.endpoint} up`
      + `, version ${this.stats.system.comfyui_version ?? 'unreported'}`
      + (device ? `, ${device.name} ${device.vram_free}/${device.vram_total} bytes free` : ', no device reported'),
    )
    this.ctx.emit('comfyui/connected', this.stats)

    // Only after a successful probe. A socket opened against an endpoint that just refused a
    // cheap GET would spend its whole reconnect budget failing and then log an error, which is
    // noise standing in for the `comfyui/unreachable` already emitted above.
    //
    // The cost, stated rather than left to be discovered: **if ComfyUI starts after the plugin
    // does, this plugin does not notice.** There is no rediscovery loop, because a poll that
    // runs forever against an endpoint nobody has configured is its own problem. Reload the
    // plugin, or call `ctx.comfyui.probe()` and then `ctx.comfyui.http.connect()`.
    this.http.connect()
  }

  /**
   * Read `GET /system_stats`.
   *
   * Blueprint: `references/ComfyUI/server.py:686` — `@routes.get("/system_stats")`. Chosen as
   * the discovery probe because it is the cheapest endpoint that proves the far end is
   * ComfyUI: it needs no graph, queues nothing, takes no lock, and exists on every build.
   * `GET /prompt` would also have answered, but it reports queue state and that is a different
   * question wearing a similar answer.
   *
   * The timeout is applied here rather than left to the platform default, which on Node is
   * effectively none for a host that accepts a connection and then says nothing.
   *
   * @returns the decoded stats body.
   * @throws ComfyDiscoveryError if the endpoint answers with a non-2xx status or a body that
   *   is not the documented object.
   * @throws ComfyUnreachableError if the endpoint does not answer within `timeoutMs`.
   */
  async probe(): Promise<ComfySystemStats> {
    try {
      return await this.http.systemStats()
    } catch (error) {
      // The client speaks in transport terms; this service's contract, and the two error
      // classes above it, speak in discovery terms. The mapping is the whole body of this
      // method because deliverable 2 moved the fetch itself into `client.ts` — leaving a
      // second implementation here would have been two places to fix a header or a timeout.
      if (error instanceof ComfyTransportError) {
        throw new ComfyUnreachableError(this.config.endpoint, error)
      }
      if (error instanceof ComfyHttpError) {
        throw new ComfyDiscoveryError(
          this.config.endpoint,
          `GET /system_stats answered ${error.status}`,
        )
      }
      if (error instanceof ComfyProtocolError) {
        throw new ComfyDiscoveryError(this.config.endpoint, error.message)
      }
      throw new ComfyDiscoveryError(
        this.config.endpoint,
        `GET /system_stats failed: ${renderThrown(error)}`,
      )
    }
  }
}

/* ------------------------------------------------------------------ entrypoint */

/**
 * Plugin entrypoint.
 *
 * Blueprint: `references/deepseek-harness/packages/interaction/tool-ask-user/src/index.ts:19`
 * — `export function apply(ctx: Context): void`, synchronous, with anything asynchronous
 * deferred to a service's `[Service.init]`.
 *
 * Constructing the service registers it: `Service`'s constructor calls
 * `ctx.reflect.provide(name, self, ...)` (`vendor/cordis/src/service.ts:57`) and the binding is
 * removed with the owning fiber. There is no `ctx.provide('comfyui', ...)` call to write and
 * no unregister to remember, which is why the instance below is constructed and not assigned.
 *
 * @param ctx - The Harness context this activation owns.
 * @param config - Raw plugin config, after {@link Config} has applied its defaults.
 */
export function apply(ctx: Context, config: ComfyPluginConfig): void {
  const resolved = resolveConfig(config)

  ctx.on('comfyui/telemetry', frame => {
    ctx.logger.debug(`comfyui: telemetry ${frame.type}`)
  })

  // Construct the bridge FIRST. The `Service` constructor is what calls
  // `ctx.reflect.provide('comfyui', self, ...)` (`vendor/cordis/src/service.ts:57`), so the
  // service exists from this line onward — and `ComfyTools` gates on `'comfyui'`. Mounting the
  // child before this would not fail loudly; the gate would simply hold it inactive, and five
  // tools would be quietly missing with nothing in the log to say why.
  new ComfyBridge(ctx, resolved)

  // Mounted as a child fiber rather than inlined, so the tool layer's dependency on
  // `ctx.tools` is its own and not the bridge's. `ctx.plugin()` takes a namespace import whole
  // — `references/deepseek-harness/packages/schedule/schedule/tests/plugin.spec.ts:9` and `:36`
  // — which is why `./tools.ts` exports `name`, `inject` and `apply` and nothing by default.
  ctx.plugin(ComfyTools)
}
