/**
 * The model-facing half of the ComfyUI bridge: five tools, a per-agent graph workspace, and a
 * local validator that mirrors ComfyUI's own so a bad graph is caught before it queues.
 *
 * ## Why this is a separate plugin from `plugin.ts`
 *
 * `inject` is a **gate**, not an import list: the fiber holds a plugin inactive until every
 * named service exists. Registering a tool requires `ctx.tools`, so this module injects it —
 * but `plugin.ts`'s `ComfyBridge` does not need the tool registry to be useful. Naming `tools`
 * on the bridge would make the whole REST surface unavailable on any deployment without a tool
 * runtime, in exchange for nothing.
 *
 * So the bridge stays ungated and mounts this module as a child fiber with
 * `ctx.plugin(ComfyTools)`. The shape is copied from
 * `references/deepseek-harness/packages/extensions/tool-cordis/src/index.ts:26-35` — a bare
 * `name`, an `inject` array, and a synchronous `apply(ctx)` — and mounted the way
 * `packages/schedule/schedule/tests/plugin.spec.ts:9` consumes such a module, as a namespace
 * import passed whole to `ctx.plugin()`. There is deliberately **no default export**; that
 * file asserts `expect('default' in toolSchedule).toBe(false)` at `:32`, so a default export
 * here would be a real incompatibility rather than a style choice.
 *
 * Injecting `'comfyui'` as well as `'tools'` is what lets every tool body below reach
 * `ctx.comfyui.http` without a null check: the gate guarantees the service is provided before
 * this fiber activates, and removes it again when the bridge unloads.
 *
 * ## What is authoritative and what is not
 *
 * {@link validateGraph} reproduces ComfyUI's validation rules against `/object_info`. It is a
 * **local pre-check** and it is never the last word: `execution.py` runs the real one, custom
 * node packs add their own `VALIDATE_INPUTS` (`references/ComfyUI/execution.py:1101`,
 * `custom_validation_failed`), and only the server knows which classes are actually installed.
 * Every finding this file produces locally is labelled `origin: 'local'`; everything read back
 * from `POST /prompt` is labelled `origin: 'server'`. They are never merged into one list,
 * because `.claude/CLAUDE.md`'s labelling rule — measured, vendor, or projected, never one
 * presented as another — applies to a validation verdict exactly as it applies to a number on
 * the site.
 *
 * ## Known limitation, stated rather than hidden
 *
 * Nothing in this file has been executed. There is no `package.json`, no `tsconfig.json` and
 * no `node_modules` under `harness/plugin-comfyui/`, and no `tsc` on this box. By
 * `.claude/CLAUDE.md`'s own standard — *"if the deliverable is a program that runs, one check
 * must be something only a real run can turn green"* — that makes this written and
 * transcription-verified, not finished.
 *
 * @module @symoneural/plugin-comfyui/tools
 */

import type { Context } from '@deepseek-ai/cordis'
import type { Agent } from '@deepseek-ai/dsh-agent'
import { defineTool } from '@deepseek-ai/dsh-tools'
import type { JsonValue, ToolExecution, ToolRunContext } from '@deepseek-ai/dsh-tools'

import { ComfyPromptRejectedError } from './client.ts'
// Type-only, and load-bearing: `plugin.ts` is where `declare module '@deepseek-ai/cordis'`
// adds `comfyui: ComfyBridge` to `Context`, so without this import `ctx.comfyui` below is not
// typed. The idiom is the reference's own —
// `references/deepseek-harness/packages/extensions/tool-cordis/src/index.ts:17` writes
// `import type {} from '@deepseek-ai/dsh-system-prompt'` for exactly this reason, to pull in an
// augmentation from a module whose values it never uses. It is erased at compile time, so the
// cycle with `plugin.ts`'s runtime import of this file is not a cycle in the emitted graph.
import type {} from './plugin.ts'
import {
  ClientId,
  type ComfyGraph,
  type ComfyInputValue,
  type ComfyNode,
  type ComfyNodeError,
  type ComfyNodeErrorReason,
  type ComfyObjectInfo,
  type ComfyPromptRequest,
  type ComfyPromptResponse,
  type ComfyTelemetryFrame,
} from './types.ts'

/**
 * Plugin name.
 *
 * Blueprint: `references/deepseek-harness/packages/extensions/tool-cordis/src/index.ts:26` —
 * a bare kebab-case string, not a package specifier.
 */
export const name = 'comfyui-harness-tools'

/**
 * Services this plugin waits for.
 *
 * Blueprint: `references/deepseek-harness/packages/extensions/tool-cordis/src/index.ts:27` —
 * `export const inject = ['tools', 'systemPrompt', 'dynamicCordisRunner', 'cordisInspect']`,
 * one entry per service the body dereferences.
 *
 * Both entries are load-bearing. `'tools'` is the registry every `register` call below needs;
 * `'comfyui'` is the bridge, and naming it here is what makes `ctx.comfyui.http` safe to read
 * inside a tool body with no defensive check — the gate holds this fiber inactive until the
 * service is provided and disposes it when the service goes away.
 */
export const inject = ['comfyui', 'tools']

/* ------------------------------------------------------------------ tuning */

/**
 * How many telemetry frames `comfy_stream_status` keeps.
 *
 * A module constant rather than a config field, deliberately. The build directive bars
 * inventing configuration properties, and `ComfyPluginConfig` in `./types.ts` has no field
 * for this; adding one would be a fabricated knob dressed as a setting. If it ever needs to be
 * tunable, that is a config-schema change made on purpose, in its own commit.
 */
const FRAME_BUFFER_SIZE = 512

/** Default page size for `comfy_list_nodes`. `/object_info` carries thousands of classes. */
const DEFAULT_NODE_PAGE = 40

/** Hard ceiling on a `comfy_list_nodes` page, whatever the caller asks for. */
const MAX_NODE_PAGE = 200

/** Longest a `comfy_stream_status` call will park waiting for a frame. */
const MAX_WAIT_MS = 120_000

/** Longest `comfy_queue_prompt` will follow a run when asked to wait. */
const MAX_FOLLOW_MS = 900_000

/* ------------------------------------------------------------------ workspace */

/**
 * The mutable graph one agent is working on.
 *
 * `comfy_load_workflow` fills it, `comfy_mutate_node` edits it, `comfy_queue_prompt` submits
 * it. Keeping it here rather than making every tool pass the whole graph in its arguments is
 * the difference between an agent editing a workflow and an agent retyping one: a FLUX graph
 * is tens of kilobytes of JSON and re-emitting it on every call would dominate the context
 * window and invite transcription errors in the parts the model was not trying to change.
 */
interface ComfyWorkspace {
  /** The graph under edit, or `undefined` before the first successful load. */
  graph: ComfyGraph | undefined
  /** Where it came from, for the record. Caller-supplied label. */
  origin: string
  /** Increments on every accepted mutation. Quoted in results so a caller can detect drift. */
  revision: number
}

/** A fresh, empty workspace. */
function emptyWorkspace(): ComfyWorkspace {
  return { graph: undefined, origin: '', revision: 0 }
}

/* ------------------------------------------------------------------ json helpers */

/**
 * Widen a checked result to `JsonValue` for a `{ type: 'json' }` output.
 *
 * Blueprint: `references/deepseek-harness/packages/extensions/tool-cordis/src/index.ts:55` —
 * `return Promise.resolve({ providers: ctx.cordisInspect.list() } as unknown as JsonValue)`.
 * `JsonValue` is a recursive union and a declared interface is not structurally assignable to
 * it, so the reference casts. This wrapper exists so that cast is written once, in a place
 * where it can be explained, instead of appearing at a dozen call sites where it would read
 * like carelessness.
 *
 * It is sound only because every object handed to it is built in this file out of strings,
 * numbers, booleans, nulls, arrays and plain objects. Nothing here forwards a class instance,
 * a `Date` or a `Map`.
 */
function toJson(value: unknown): JsonValue {
  return value as JsonValue
}

/**
 * Deep-copy a graph.
 *
 * `structuredClone` is a global on the runtimes this harness declares support for:
 * `references/deepseek-harness/package.json:8-10` pins
 * `"engines": {"node": "^22.19.0 || >=24.0.0"}`, and the global has been available and
 * unflagged since node 17. Unlike the `WebSocket` global that `client.ts` has to guard for,
 * this one is present on **this** box too (node v20.19.2), so no fallback is warranted and a
 * hand-rolled recursive copy would only be a second implementation to keep correct.
 *
 * The copy is what makes rollback real. A shallow copy of a `Record` shares every node object,
 * so restoring it would restore a graph whose nodes had already been mutated in place — a
 * rollback that reports success and changes nothing is worse than no rollback at all.
 */
function cloneGraph(graph: ComfyGraph): ComfyGraph {
  return structuredClone(graph)
}

/** Render anything a `catch` can bind, without assuming it is an `Error`. */
function renderThrown(value: unknown): string {
  if (value instanceof Error) return value.message
  if (typeof value === 'string') return value
  try {
    return JSON.stringify(value) ?? String(value)
  } catch {
    return String(value)
  }
}

/**
 * Build one validation complaint in ComfyUI's own shape.
 *
 * Every field matches {@link ComfyNodeErrorReason}, which is
 * `references/ComfyUI/execution.py`'s dict written as a type. Local findings reuse the
 * server's tag vocabulary rather than inventing one so that a caller — or a model — reads the
 * same word for the same fault whichever side found it.
 */
function reason(
  type: string,
  message: string,
  details: string,
  extra: Record<string, unknown> = {},
): ComfyNodeErrorReason {
  return { type, message, details, extra_info: extra }
}

/* ------------------------------------------------------------------ input spec reading */

/**
 * One input slot as `/object_info` describes it.
 *
 * Blueprint: `references/ComfyUI/server.py:751-796` (`def node_info`) assembles `input` from
 * the node class's `INPUT_TYPES()`, whose values are tuples. The first element is either a
 * type name (`"INT"`, `"MODEL"`, ...) or a **list of permitted values** — that list is how a
 * combo widget is declared, and it is why `value_not_in_list` exists at
 * `references/ComfyUI/execution.py:1070`. The optional second element is a dict of constraints
 * (`min`, `max`, `default`, ...).
 *
 * Typed loosely on purpose: this is third-party data that custom node packs extend freely, so
 * every read below is guarded and an unreadable spec yields no finding rather than a wrong one.
 */
interface InputSpec {
  /** Declared type name, when the first tuple element is a string. */
  typeName?: string
  /** Permitted values, when the first tuple element is a list. */
  choices?: unknown[]
  /** Constraint dict from the second tuple element. */
  options: Record<string, unknown>
}

/** Read one `INPUT_TYPES` tuple, tolerating every shape a custom pack might have written. */
function readInputSpec(raw: unknown): InputSpec {
  if (!Array.isArray(raw)) return { options: {} }
  const head = raw[0]
  const opts = raw[1]
  const options = typeof opts === 'object' && opts !== null ? (opts as Record<string, unknown>) : {}
  if (Array.isArray(head)) return { choices: head, options }
  if (typeof head === 'string') return { typeName: head, options }
  return { options }
}

/** Pull a numeric constraint off an options dict, ignoring anything non-finite. */
function numericOption(options: Record<string, unknown>, key: string): number | undefined {
  const value = options[key]
  return typeof value === 'number' && Number.isFinite(value) ? value : undefined
}

/* ------------------------------------------------------------------ value classification */

/**
 * How a caller intends a value to be read on the wire.
 *
 * This enum exists because of a genuine ambiguity in ComfyUI's format that no amount of
 * careful typing removes: `references/ComfyUI/execution.py:917` is `if isinstance(val, list):`
 * and that is the *entire* test for "is this input a link". There is no tag and no marker key,
 * so a JSON array meant as a literal value — a resolution pair, a list widget's selection — is
 * indistinguishable from a link to a node's output, and the server resolves it as a link every
 * time.
 *
 * `references/ComfyUI/execution.py:983-989` provides the escape hatch and states the reason in
 * its own comment: *"as by default list value is reserved to represent the connection between
 * nodes"*. A literal array must arrive wrapped as `{"__value__": [...]}`.
 *
 * Making the caller name its intent is therefore not ceremony. The alternative — inferring
 * from the JavaScript type — silently picks `link` for every array, which is the wrong answer
 * for list widgets and fails one layer away from the mistake, as a missing-node error against
 * a node id the caller never mentioned.
 */
type ValueKind = 'literal' | 'link' | 'boxed_literal'

/** Result of turning a caller's `(value_kind, value)` pair into something writable. */
type CoercionResult =
  | { ok: true; value: ComfyInputValue }
  | { ok: false; violations: ComfyNodeErrorReason[] }

/**
 * Turn a caller's declared intent into a value the server will read the same way.
 *
 * The `link` branch enforces length 2 locally rather than letting the server say
 * `bad_linked_input` (`references/ComfyUI/execution.py:919-930`), because catching it here
 * means the workspace graph never holds a shape that cannot queue.
 */
function coerceValue(kind: ValueKind, raw: unknown, inputName: string): CoercionResult {
  if (kind === 'link') {
    if (!Array.isArray(raw) || raw.length !== 2) {
      return {
        ok: false,
        violations: [
          reason(
            'bad_linked_input',
            'Bad linked input, must be a length-2 list of [node_id, slot_index]',
            inputName,
            { input_name: inputName, received_value: raw },
          ),
        ],
      }
    }
    const [sourceId, slot] = raw
    if (typeof sourceId !== 'string' || typeof slot !== 'number' || !Number.isInteger(slot)) {
      return {
        ok: false,
        violations: [
          reason(
            'bad_linked_input',
            'A link must be [node_id: string, slot_index: integer]',
            inputName,
            { input_name: inputName, received_value: raw },
          ),
        ],
      }
    }
    return { ok: true, value: [sourceId, slot] }
  }

  if (kind === 'boxed_literal') {
    return { ok: true, value: { __value__: raw } }
  }

  // kind === 'literal'
  if (Array.isArray(raw)) {
    return {
      ok: false,
      violations: [
        reason(
          'bad_linked_input',
          'A bare JSON array in an input slot is read as a node link, never as a literal',
          `${inputName}: pass value_kind "boxed_literal" to send this array as a value, or ` +
            '"link" if it really is [node_id, slot_index]',
          { input_name: inputName, received_value: raw },
        ),
      ],
    }
  }
  if (typeof raw === 'object' && raw !== null) {
    return { ok: true, value: raw as Record<string, unknown> }
  }
  if (raw === null || typeof raw === 'string' || typeof raw === 'number' || typeof raw === 'boolean') {
    return { ok: true, value: raw }
  }
  return {
    ok: false,
    violations: [
      reason('invalid_input_type', 'Value is not representable as JSON', inputName, {
        input_name: inputName,
        received_type: typeof raw,
      }),
    ],
  }
}

/** True when a stored input value is a node link. Mirrors `execution.py:917`. */
function isLink(value: ComfyInputValue): value is [string, number] {
  return Array.isArray(value)
}

/* ------------------------------------------------------------------ graph validation */

/** A whole-graph verdict: per-node complaints plus faults that belong to no single node. */
interface GraphVerdict {
  /** True when nothing at all was found. */
  ok: boolean
  /** Where these findings came from. Never mixed with the other origin in one list. */
  origin: 'local' | 'server'
  /** Faults that belong to the graph rather than to a node, e.g. `prompt_no_outputs`. */
  graph_errors: ComfyNodeErrorReason[]
  /** Per-node complaints, in ComfyUI's own shape. */
  node_errors: Record<string, ComfyNodeError>
}

/**
 * Check a graph against `/object_info` the way `execution.py` will.
 *
 * This is the "execution validation handler" the build directive asks for, and every rule it
 * applies is one the server applies, with the tag the server uses:
 *
 * | rule | server site |
 * |---|---|
 * | unknown `class_type` | `execution.py:1151-1161` `missing_node_type` |
 * | absent `class_type` | `execution.py:1134-1144` `missing_node_type` |
 * | required input absent | `execution.py:905` `required_input_missing` |
 * | array input not length 2 | `execution.py:919-930` `bad_linked_input` |
 * | link to a node not in the graph | `execution.py:932` (`prompt[o_id]`, a raw `KeyError`) |
 * | literal outside a combo's list | `execution.py:1070` `value_not_in_list` |
 * | number below `min` | `execution.py:1022` `value_smaller_than_min` |
 * | number above `max` | `execution.py:1035` `value_bigger_than_max` |
 * | no output node at all | `execution.py:1169` `prompt_no_outputs` |
 *
 * Two things it deliberately does **not** do. It does not run any node's own
 * `VALIDATE_INPUTS` — that is `custom_validation_failed` (`execution.py:1101`) and it is
 * arbitrary Python that only the server can execute. And it does not check output *types*
 * across a link (`return_type_mismatch`, `execution.py:940`) unless both classes are present
 * in `/object_info`, since the receiving type list is what the server compares against.
 *
 * So a clean verdict here means "nothing this side can see is wrong", never "this will run".
 * That distinction is carried in the result rather than in a comment: `origin` is `'local'`,
 * and every caller renders it with that word attached.
 */
function validateGraph(graph: ComfyGraph, objectInfo: ComfyObjectInfo): GraphVerdict {
  const nodeErrors: Record<string, ComfyNodeError> = {}
  const graphErrors: ComfyNodeErrorReason[] = []

  const add = (nodeId: string, classType: string, found: ComfyNodeErrorReason[]): void => {
    if (found.length === 0) return
    const existing = nodeErrors[nodeId]
    if (existing) {
      existing.errors.push(...found)
      return
    }
    nodeErrors[nodeId] = { errors: found, dependent_outputs: [], class_type: classType }
  }

  let sawOutputNode = false

  for (const [nodeId, node] of Object.entries(graph)) {
    const found: ComfyNodeErrorReason[] = []
    const classType = typeof node.class_type === 'string' ? node.class_type : ''

    if (classType === '') {
      add(nodeId, '', [
        reason(
          'missing_node_type',
          'Cannot execute because a node is missing the class_type property.',
          `Node ID '#${nodeId}'`,
          { node_id: nodeId },
        ),
      ])
      continue
    }

    const definition = objectInfo[classType]
    if (definition === undefined) {
      add(nodeId, classType, [
        reason(
          'missing_node_type',
          `Cannot execute because node ${classType} does not exist.`,
          `Node ID '#${nodeId}'`,
          { node_id: nodeId, class_type: classType },
        ),
      ])
      continue
    }
    if (definition.output_node === true) sawOutputNode = true

    const inputs = node.inputs ?? {}
    const required = definition.input?.required ?? {}
    const optional = definition.input?.optional ?? {}

    for (const inputName of Object.keys(required)) {
      if (!(inputName in inputs)) {
        found.push(
          reason(
            'required_input_missing',
            `Required input is missing: ${inputName}`,
            inputName,
            { input_name: inputName },
          ),
        )
      }
    }

    for (const [inputName, value] of Object.entries(inputs)) {
      const rawSpec = required[inputName] ?? optional[inputName]
      if (isLink(value)) {
        const [sourceId] = value
        if (!(sourceId in graph)) {
          // The server does not tag this one: `execution.py:932` indexes `prompt[o_id]`
          // directly, so a dangling link is a bare KeyError caught by the outer
          // `exception_during_inner_validation` handler at `:967`. Catching it here turns an
          // opaque traceback into the sentence that names the input and the missing node.
          found.push(
            reason(
              'bad_linked_input',
              `Input ${inputName} links to node '${sourceId}', which is not in this graph`,
              inputName,
              { input_name: inputName, received_value: value, missing_node_id: sourceId },
            ),
          )
        }
        continue
      }
      if (rawSpec === undefined) continue

      const spec = readInputSpec(rawSpec)
      const literal = unboxed(value)

      if (spec.choices !== undefined && !spec.choices.includes(literal)) {
        found.push(
          reason(
            'value_not_in_list',
            `Value not in list: ${inputName}`,
            `${inputName}: '${String(literal)}' not in ${JSON.stringify(spec.choices.slice(0, 20))}`,
            { input_name: inputName, received_value: literal },
          ),
        )
      }
      if (typeof literal === 'number') {
        const min = numericOption(spec.options, 'min')
        const max = numericOption(spec.options, 'max')
        if (min !== undefined && literal < min) {
          found.push(
            reason(
              'value_smaller_than_min',
              `Value ${literal} smaller than min of ${min}`,
              inputName,
              { input_name: inputName, received_value: literal },
            ),
          )
        }
        if (max !== undefined && literal > max) {
          found.push(
            reason(
              'value_bigger_than_max',
              `Value ${literal} bigger than max of ${max}`,
              inputName,
              { input_name: inputName, received_value: literal },
            ),
          )
        }
      }
    }

    add(nodeId, classType, found)
  }

  if (!sawOutputNode && Object.keys(graph).length > 0) {
    graphErrors.push(
      reason(
        'prompt_no_outputs',
        'Prompt has no outputs',
        'No node in this graph is registered with output_node true, so executing it would ' +
          'produce nothing. Add a SaveImage, PreviewImage or equivalent terminal node.',
      ),
    )
  }

  attachDependentOutputs(graph, objectInfo, nodeErrors)

  return {
    ok: graphErrors.length === 0 && Object.keys(nodeErrors).length === 0,
    origin: 'local',
    graph_errors: graphErrors,
    node_errors: nodeErrors,
  }
}

/** Strip a `__value__` box for comparison against a spec. Mirrors `execution.py:985-988`. */
function unboxed(value: ComfyInputValue): unknown {
  if (typeof value === 'object' && value !== null && !Array.isArray(value) && '__value__' in value) {
    return (value as { __value__: unknown }).__value__
  }
  return value
}

/**
 * Fill in each failing node's `dependent_outputs`.
 *
 * Blueprint: `references/ComfyUI/execution.py:1216-1228` — the server records, for each
 * rejected node, the output nodes that were depending on it. That field is the one that makes
 * a partial acceptance legible, so a local verdict that omitted it would be shaped like the
 * server's and mean less.
 *
 * Computed by walking *forward*: a node's `inputs` name the nodes it consumes, so consumers
 * are found by inverting that relation and then taking the transitive closure. `seen` makes
 * the walk terminate on a cyclic graph rather than recursing forever — cycles are a real graph
 * fault the server itself reports as `dependency_cycle` (`execution.py:860`), which means this
 * function must survive one in order to describe the graph that has it.
 */
function attachDependentOutputs(
  graph: ComfyGraph,
  objectInfo: ComfyObjectInfo,
  nodeErrors: Record<string, ComfyNodeError>,
): void {
  const consumers = new Map<string, string[]>()
  for (const [nodeId, node] of Object.entries(graph)) {
    for (const value of Object.values(node.inputs ?? {})) {
      if (!isLink(value)) continue
      const sourceId = value[0]
      const list = consumers.get(sourceId)
      if (list) list.push(nodeId)
      else consumers.set(sourceId, [nodeId])
    }
  }

  for (const [nodeId, record] of Object.entries(nodeErrors)) {
    const outputs: string[] = []
    const seen = new Set<string>([nodeId])
    const queue = [...(consumers.get(nodeId) ?? [])]
    while (queue.length > 0) {
      const next = queue.shift()
      if (next === undefined || seen.has(next)) continue
      seen.add(next)
      const classType = graph[next]?.class_type
      if (classType !== undefined && objectInfo[classType]?.output_node === true) outputs.push(next)
      queue.push(...(consumers.get(next) ?? []))
    }
    record.dependent_outputs = outputs
  }
}

/* ------------------------------------------------------------------ graph shape check */

/**
 * Establish that an arbitrary JSON document is an API-format prompt graph.
 *
 * The check matters because there are **two** ComfyUI graph formats and only one is accepted
 * here. `references/ComfyUI/server.py:1112` hands the posted `prompt` straight to
 * `validate_prompt`, which indexes `node['class_type']` — that is the API format, node id →
 * node. The editor's own save format is a different document, with top-level `nodes` and
 * `links` arrays, and posting it produces a wall of `missing_node_type` complaints that read
 * as though every class in the graph were uninstalled.
 *
 * Naming that specific confusion in the failure message is the point of doing the check here
 * rather than letting the server do it: the server's answer is technically correct and
 * completely misleading.
 */
function readGraph(raw: unknown): { ok: true; graph: ComfyGraph } | { ok: false; detail: string } {
  if (typeof raw !== 'object' || raw === null || Array.isArray(raw)) {
    return { ok: false, detail: 'the graph must be a JSON object of node id → node' }
  }
  const record = raw as Record<string, unknown>
  if ('nodes' in record && 'links' in record) {
    return {
      ok: false,
      detail:
        'this looks like the ComfyUI *editor* workflow format (top-level "nodes" and "links"), ' +
        'not the API format. Only the API format can be posted to /prompt — export it with the ' +
        'editor\'s "Save (API Format)", or enable Settings → Dev mode API options.',
    }
  }
  const graph: ComfyGraph = {}
  for (const [nodeId, value] of Object.entries(record)) {
    if (typeof value !== 'object' || value === null || Array.isArray(value)) {
      return { ok: false, detail: `node '${nodeId}' is not an object` }
    }
    const node = value as { class_type?: unknown; inputs?: unknown; _meta?: unknown }
    if (typeof node.class_type !== 'string') {
      return { ok: false, detail: `node '${nodeId}' has no string class_type` }
    }
    if (node.inputs !== undefined && (typeof node.inputs !== 'object' || node.inputs === null)) {
      return { ok: false, detail: `node '${nodeId}' has a non-object inputs` }
    }
    // Normalised rather than cast. `ComfyNode.inputs` is not optional, and a node object that
    // genuinely lacks the key — legal on the wire for a node with no inputs — would otherwise
    // be asserted into a type that promises it, leaving every reader downstream free to index
    // a value that is not there. Filling it in here is the difference between the type being
    // true and the type being claimed.
    const normalised: ComfyNode = {
      class_type: node.class_type,
      inputs: (node.inputs as Record<string, ComfyInputValue> | undefined) ?? {},
    }
    if (typeof node._meta === 'object' && node._meta !== null) {
      normalised._meta = node._meta as { title?: string }
    }
    graph[nodeId] = normalised
  }
  if (Object.keys(graph).length === 0) {
    return { ok: false, detail: 'the graph is empty' }
  }
  return { ok: true, graph }
}

/* ------------------------------------------------------------------ cancellation */

/**
 * Reject as soon as `exec.signal` aborts, so a parked tool settles on cancellation.
 *
 * `references/deepseek-harness/packages/core/tools/README.md` is explicit that every async
 * tool must observe or forward the signal and settle only after its own work stops. Two tools
 * here park on time rather than on a network call — `comfy_stream_status`'s wait and
 * `comfy_queue_prompt`'s follow — and a bare `setTimeout` in either would hold the execution
 * open past a cancellation with nothing left to cancel.
 *
 * The listener is removed in `finally` on every path. Without that, a long-lived signal would
 * accumulate one listener per call and node would eventually warn about a leak on an
 * `AbortSignal` that is behaving perfectly.
 */
function abortable<T>(signal: AbortSignal, body: (resolve: (value: T) => void) => () => void): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    if (signal.aborted) {
      reject(new Error('cancelled'))
      return
    }
    // `dispose` is captured in a mutable binding and `settled` guards the ordering, because
    // `body` is allowed to call its `resolve` synchronously. If it does, the settle path runs
    // before `dispose` has been assigned; without the guard it would call an undefined
    // disposer, and with a naive `cleanup` no-op placeholder it would silently leak the abort
    // listener instead. `settled` also makes the disposer run exactly once on every path.
    let dispose: (() => void) | undefined
    let settled = false
    const finish = (): void => {
      if (settled) return
      settled = true
      signal.removeEventListener('abort', onAbort)
      dispose?.()
    }
    function onAbort(): void {
      finish()
      reject(new Error('cancelled'))
    }
    signal.addEventListener('abort', onAbort, { once: true })
    dispose = body(value => {
      finish()
      resolve(value)
    })
    if (settled) dispose()
  })
}

/* ------------------------------------------------------------------ entrypoint */

/**
 * Register the five ComfyUI tools.
 *
 * Blueprint: `references/deepseek-harness/packages/extensions/tool-cordis/src/index.ts:35` —
 * `export function apply(ctx: Context): void`, synchronous, with every registration a
 * `ctx.tools.register(defineTool({...}))` call whose returned disposer is discarded because
 * the registration is already owned by the calling fiber.
 *
 * @param ctx - the Harness context this activation owns.
 */
export function apply(ctx: Context): void {
  /* --- per-agent workspace -------------------------------------------------- */

  /**
   * One workspace per agent.
   *
   * Keyed on the `Agent` object itself, which
   * `references/deepseek-harness/packages/extensions/tool-cordis/src/index.ts:29-32`
   * establishes is a stable object identity a tool body can hold — `requireAgent(exec)`
   * returns it and threads it into `listPlugins(agent)` / `inspectPlugin(agent, pluginId)` as
   * the discriminator for exactly this kind of per-agent state.
   *
   * A `WeakMap` rather than a `Map` so an agent that goes away takes its graph with it. A
   * single shared workspace would be a correctness bug and not merely a limitation: two agents
   * editing concurrently would each see the other's nodes appear, and `comfy_queue_prompt`
   * would submit a graph nobody wrote.
   */
  const workspaces = new WeakMap<Agent, ComfyWorkspace>()

  /**
   * The workspace for calls that arrive without an agent.
   *
   * `ToolExecution.agent` is optional
   * (`references/deepseek-harness/packages/core/tools/src/index.ts:325`), so an agentless
   * dispatch is a shape the registry supports and this file must answer for. It gets one
   * shared workspace, which is the honest arrangement: there is no identity to separate such
   * callers by, so inventing one would be pretending to an isolation that does not exist.
   */
  const sessionless = emptyWorkspace()

  const workspaceFor = (exec: ToolExecution): ComfyWorkspace => {
    if (exec.agent === undefined) return sessionless
    const existing = workspaces.get(exec.agent)
    if (existing) return existing
    const fresh = emptyWorkspace()
    workspaces.set(exec.agent, fresh)
    return fresh
  }

  /** Fetch the workspace graph or explain precisely what the caller has to do first. */
  const requireGraph = (workspace: ComfyWorkspace): ComfyGraph => {
    if (workspace.graph === undefined) {
      throw new Error(
        'No workflow is loaded in this session. Call comfy_load_workflow with an API-format ' +
          'graph before mutating or queueing.',
      )
    }
    return workspace.graph
  }

  /* --- telemetry ring buffer ------------------------------------------------ */

  /** One buffered frame, with a monotonic sequence a caller can resume from. */
  interface BufferedFrame {
    seq: number
    /** `'frame'` for engine telemetry, `'gap'` for a socket drop. Never conflated. */
    kind: 'frame' | 'gap'
    /** Engine frame type, or `comfyui/disconnected` for a gap marker. */
    type: string
    /** The payload, forwarded unchanged. */
    data: unknown
  }

  const frames: BufferedFrame[] = []
  let sequence = 0
  const waiters = new Set<() => void>()

  const push = (kind: BufferedFrame['kind'], type: string, data: unknown): void => {
    sequence += 1
    frames.push({ seq: sequence, kind, type, data })
    // Bounded, and the oldest goes first. An unbounded buffer on a long-running session is a
    // slow leak that only shows up under exactly the workload this plugin exists for: a long
    // render emits a progress frame per step.
    while (frames.length > FRAME_BUFFER_SIZE) frames.shift()
    for (const wake of [...waiters]) wake()
  }

  // `ctx.on` registrations are owned by this fiber and removed when it unloads, the same way
  // `./plugin.ts:394` registers its debug listener. There is no manual disposer to hold.
  ctx.on('comfyui/telemetry', (frame: ComfyTelemetryFrame) => {
    push('frame', frame.type, frame.data)
  })

  ctx.on('comfyui/disconnected', detail => {
    // Recorded as a `gap`, never as a frame. Frames that arrived while the socket was down are
    // gone; `GET /history/{prompt_id}` is the durable record. Marking the hole is the honest
    // move, and synthesising anything to fill it is the dishonest one `.claude/CLAUDE.md`
    // bars — the same reasoning `client.ts` applies where the gap originates.
    push('gap', 'comfyui/disconnected', detail)
  })

  /** Frames after `since`, oldest first, capped. */
  const framesSince = (since: number, limit: number, promptId?: string): BufferedFrame[] => {
    const matches = frames.filter(frame => {
      if (frame.seq <= since) return false
      if (promptId === undefined) return true
      const data = frame.data
      if (typeof data !== 'object' || data === null) return false
      return (data as { prompt_id?: unknown }).prompt_id === promptId
    })
    return matches.slice(0, limit)
  }

  /* --- shared object_info cache --------------------------------------------- */

  /**
   * `/object_info` for the current process, fetched at most once per `maxAgeMs`.
   *
   * The document is large — thousands of classes, each with full input tuples — and three of
   * the five tools need it. Re-fetching per call would make `comfy_mutate_node` a
   * multi-megabyte round trip for a one-field edit.
   *
   * The cache is time-bounded rather than permanent because a ComfyUI restart can change what
   * is installed, and a stale cache would then report `missing_node_type` for a class that
   * exists, or accept one that no longer does.
   */
  let objectInfoCache: { at: number; value: ComfyObjectInfo } | undefined
  const OBJECT_INFO_TTL_MS = 60_000

  const objectInfo = async (signal: AbortSignal, refresh = false): Promise<ComfyObjectInfo> => {
    const now = Date.now()
    if (!refresh && objectInfoCache && now - objectInfoCache.at < OBJECT_INFO_TTL_MS) {
      return objectInfoCache.value
    }
    const value = await ctx.comfyui.http.objectInfo(signal)
    objectInfoCache = { at: now, value }
    return value
  }

  /* --- tool 1: comfy_list_nodes --------------------------------------------- */

  ctx.tools.register(
    defineTool({
      name: 'comfy_list_nodes',
      description:
        'Discover which node classes this ComfyUI install actually has, from its live ' +
        '/object_info. Call this before writing or editing a graph: class names are not ' +
        'portable between installs, custom node packs add and remove them, and a class that ' +
        'is not installed fails validation as missing_node_type. Pass node_class to get one ' +
        "class's full definition including every input, its type, and its permitted values or " +
        'min/max. Pass search or category to browse; results are paged and always report the ' +
        'total so a capped page is never mistaken for the whole set.',
      parameters: {
        node_class: {
          type: 'string',
          description:
            'Exact class name for a full definition, e.g. "KSampler". Overrides search and ' +
            'category. Use this to read the input names comfy_mutate_node will accept.',
        },
        search: {
          type: 'string',
          description:
            'Case-insensitive substring matched against class name, display name and ' +
            'description.',
        },
        category: {
          type: 'string',
          description: 'Case-insensitive prefix match on the node category, e.g. "sampling".',
        },
        output_only: {
          type: 'boolean',
          description:
            'Return only terminal nodes (output_node true). A graph with none of these is ' +
            'rejected as prompt_no_outputs.',
        },
        limit: {
          type: 'integer',
          description: `Page size. Default ${DEFAULT_NODE_PAGE}, hard maximum ${MAX_NODE_PAGE}.`,
        },
        offset: { type: 'integer', description: 'Zero-based index of the first result to return.' },
      },
      output: {
        schema: { type: 'json' },
        render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      // Reads /object_info and nothing else. It touches no workspace and queues no work, so it
      // is safe to dispatch alongside other calls. The README's bar for opting in is that the
      // body does not mutate parent-owned state; this one does not.
      isConcurrencySafe: () => true,
      async execute(args, exec: ToolRunContext) {
        const info = await objectInfo(exec.signal)

        const wanted = args.node_class
        if (wanted !== undefined) {
          const definition = info[wanted]
          if (definition === undefined) {
            // Bound to a local rather than written `args.node_class!`. Narrowing on a property
            // does not survive into a callback, so the assertion would have been the only way
            // to keep the `.filter` compiling — and a non-null assertion is a claim the
            // compiler stops checking. The local is checked once and stays narrowed.
            const near = Object.keys(info)
              .filter(key => key.toLowerCase().includes(wanted.toLowerCase()))
              .slice(0, 10)
            throw new Error(
              `comfyui has no node class '${wanted}'.` +
                (near.length > 0 ? ` Did you mean: ${near.join(', ')}?` : ''),
            )
          }
          return toJson({ node_class: wanted, definition })
        }

        const search = args.search?.toLowerCase()
        const category = args.category?.toLowerCase()
        const matches = Object.entries(info).filter(([className, definition]) => {
          if (args.output_only === true && definition.output_node !== true) return false
          if (category !== undefined && !(definition.category ?? '').toLowerCase().startsWith(category)) {
            return false
          }
          if (search === undefined) return true
          const haystack = `${className} ${definition.display_name ?? ''} ${definition.description ?? ''}`
          return haystack.toLowerCase().includes(search)
        })

        const limit = Math.min(Math.max(args.limit ?? DEFAULT_NODE_PAGE, 1), MAX_NODE_PAGE)
        const offset = Math.max(args.offset ?? 0, 0)
        const page = matches.slice(offset, offset + limit)

        return toJson({
          // `total` and `truncated` are not optional politeness. `.claude/CLAUDE.md` bars
          // silent caps, and a page of 40 out of 900 presented without them reads as the
          // complete set — which would send a model looking for a class that is installed and
          // simply was not on this page.
          total: matches.length,
          returned: page.length,
          offset,
          truncated: offset + page.length < matches.length,
          nodes: page.map(([className, definition]) => ({
            class_type: className,
            display_name: definition.display_name ?? className,
            category: definition.category ?? '',
            output_node: definition.output_node === true,
            required_inputs: Object.keys(definition.input?.required ?? {}),
            optional_inputs: Object.keys(definition.input?.optional ?? {}),
            outputs: definition.output_name ?? [],
            description: firstLine(definition.description ?? ''),
          })),
        })
      },
      presentCall: args => ({
        card: 'generic',
        title: args.node_class !== undefined ? `comfy node ${args.node_class}` : 'comfy node list',
        kind: 'search',
        rawInput: args.node_class ?? args.search ?? args.category ?? '',
      }),
    }),
  )

  /* --- tool 2: comfy_load_workflow ------------------------------------------ */

  ctx.tools.register(
    defineTool({
      name: 'comfy_load_workflow',
      description:
        'Load an API-format ComfyUI graph into this session as the working graph, replacing ' +
        'whatever was loaded before. The graph must be the API ' +
        'format (a JSON object of node id → {class_type, inputs}), not the editor save format ' +
        'with top-level "nodes" and "links". It is validated against the live /object_info and ' +
        'the findings are returned, but a graph with findings is still loaded so it can be ' +
        'repaired with comfy_mutate_node. Validation here is local and advisory; the server ' +
        'runs the authoritative check when the graph is queued.',
      parameters: {
        graph: {
          type: 'json',
          required: true,
          description:
            'The API-format graph: {"3": {"class_type": "KSampler", "inputs": {...}}, ...}.',
        },
        origin: {
          type: 'string',
          description:
            'Free-text label recording where this graph came from. Echoed back on later calls.',
        },
        validate: {
          type: 'boolean',
          description:
            'Check the graph against /object_info while loading. Default true. Set false only ' +
            'to load a graph while ComfyUI is unreachable.',
        },
      },
      output: {
        schema: { type: 'json' },
        render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      // No isConcurrencySafe: this replaces session-owned state. Two loads dispatched together
      // would leave the workspace holding whichever finished last, with no way to tell which.
      async execute(args, exec: ToolRunContext) {
        const parsed = readGraph(args.graph)
        if (!parsed.ok) {
          throw new Error(`comfy_load_workflow: ${parsed.detail}`)
        }

        const workspace = workspaceFor(exec)
        workspace.graph = cloneGraph(parsed.graph)
        workspace.origin = args.origin ?? 'inline'
        workspace.revision = 1

        const summary = summarise(workspace.graph)
        if (args.validate === false) {
          return toJson({
            loaded: true,
            revision: workspace.revision,
            origin: workspace.origin,
            validation: { skipped: true, reason: 'validate was set false by the caller' },
            ...summary,
          })
        }

        let verdict: GraphVerdict | { unavailable: string }
        try {
          verdict = validateGraph(workspace.graph, await objectInfo(exec.signal))
        } catch (error) {
          // Cancellation is not an unreachable engine; report it as itself rather than as a
          // successful load with an advisory note. The graph is already in the workspace by
          // this point — a load is not undone by cancelling its validation — but the caller
          // gets the abort it asked for instead of a result it did not wait for.
          if (exec.signal.aborted) throw error
          // Unreachable engine is not a bad graph, and reporting it as one would send a caller
          // rewriting a workflow that is fine. The graph stays loaded either way.
          verdict = { unavailable: renderThrown(error) }
        }

        return toJson({
          loaded: true,
          revision: workspace.revision,
          origin: workspace.origin,
          validation: verdict,
          ...summary,
        })
      },
      presentCall: args => ({
        card: 'generic',
        title: `comfy load workflow${args.origin !== undefined ? ` (${args.origin})` : ''}`,
        kind: 'edit',
      }),
    }),
  )

  /* --- tool 3: comfy_mutate_node -------------------------------------------- */

  ctx.tools.register(
    defineTool({
      name: 'comfy_mutate_node',
      description:
        'Change one input on one node of the loaded graph, or retitle it. The mutation is ' +
        'applied to a snapshot, the node is re-validated against its /object_info definition, ' +
        'and by default an invalid result is rolled back so the working graph is never left ' +
        'in a state that cannot queue. IMPORTANT: value_kind is required and decides how the ' +
        'server reads the value. A bare JSON array in an input slot is always read as a node ' +
        'link [node_id, output_index], never as a literal value, so an array you mean as a ' +
        'value must be sent with value_kind "boxed_literal". Call comfy_list_nodes with ' +
        "node_class first to read the exact input names and permitted values for this node's " +
        'class.',
      parameters: {
        node_id: {
          type: 'string',
          required: true,
          description: 'Key of the node in the loaded graph, e.g. "3".',
        },
        input: {
          type: 'string',
          description:
            'Name of the input slot to set, exactly as /object_info spells it. Required ' +
            'unless only set_title is given.',
        },
        value_kind: {
          type: 'string',
          enum: ['literal', 'link', 'boxed_literal'],
          description:
            'How the server must read this value. "literal" for a string, number, boolean or ' +
            'null. "link" for [node_id, output_index] connecting another node\'s output. ' +
            '"boxed_literal" for an array or object that is a value rather than a link; it is ' +
            'sent wrapped as {"__value__": ...}, which ComfyUI unwraps on receipt. Required ' +
            'whenever input is given.',
        },
        value: {
          type: 'json',
          description: 'The value itself, interpreted according to value_kind.',
        },
        set_title: {
          type: 'string',
          description: "Set the node's display title (_meta.title). May be used alone.",
        },
        rollback: {
          type: 'boolean',
          description:
            'Undo this mutation automatically if it leaves the node invalid. Default true. ' +
            'Set false to keep an intermediate state while making a multi-step edit whose ' +
            'steps are individually invalid.',
        },
      },
      output: {
        schema: { type: 'json' },
        render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      // No isConcurrencySafe: mutates the session graph. Two concurrent mutations against one
      // snapshot would silently drop one of them.
      async execute(args, exec: ToolRunContext) {
        const workspace = workspaceFor(exec)
        const graph = requireGraph(workspace)

        const node = graph[args.node_id]
        if (node === undefined) {
          throw new Error(
            `comfy_mutate_node: the loaded graph has no node '${args.node_id}'. ` +
              `It has ${Object.keys(graph).length}: ${Object.keys(graph).slice(0, 24).join(', ')}`,
          )
        }
        if (args.input === undefined && args.set_title === undefined) {
          throw new Error('comfy_mutate_node: give input (with value_kind) or set_title, or both.')
        }
        if (args.input !== undefined && args.value_kind === undefined) {
          throw new Error(
            'comfy_mutate_node: value_kind is required whenever input is given. Use "literal" ' +
              'for a scalar, "link" for [node_id, output_index], or "boxed_literal" for an ' +
              'array or object that is a value rather than a link.',
          )
        }

        // Snapshot BEFORE anything is touched, and snapshot a deep copy. This is the whole
        // rollback mechanism; see `cloneGraph` for why a shallow copy would make it a no-op
        // that reports success. It lives for this call only — there is no undo stack, because
        // a stack nothing pops is 32 cloned graphs held per agent in exchange for nothing.
        const snapshot = cloneGraph(graph)

        const applied: Record<string, unknown> = {}
        if (args.input !== undefined && args.value_kind !== undefined) {
          const coerced = coerceValue(args.value_kind as ValueKind, args.value, args.input)
          if (!coerced.ok) {
            // Rejected before the graph was touched, so there is nothing to roll back and the
            // snapshot is discarded. Reported in the same vocabulary as a rollback so a caller
            // does not need two code paths to read a refusal.
            return toJson({
              applied: false,
              rolled_back: false,
              reason: 'the value could not be represented as requested',
              revision: workspace.revision,
              validation: {
                ok: false,
                origin: 'local',
                graph_errors: [],
                node_errors: {
                  [args.node_id]: {
                    errors: coerced.violations,
                    dependent_outputs: [],
                    class_type: node.class_type,
                  },
                },
              },
            })
          }
          node.inputs[args.input] = coerced.value
          applied[args.input] = coerced.value
        }

        if (args.set_title !== undefined) {
          node._meta = { ...node._meta, title: args.set_title }
          applied['_meta.title'] = args.set_title
        }

        // Re-validate. An engine that cannot be reached leaves the mutation standing: it was
        // asked for, it was applied, and "I could not check" is not "it was wrong". Saying so
        // explicitly is better than a rollback the caller cannot account for.
        let verdict: GraphVerdict
        try {
          verdict = validateGraph(graph, await objectInfo(exec.signal))
        } catch (error) {
          // Cancellation lands here too, and it is not an unreachable engine. Forwarding
          // `exec.signal` into `objectInfo` is not the same as honouring it: without this
          // branch an abort mid-fetch would leave the edit applied, bump the revision and
          // return `applied: true` for a call the registry has already marked cancelled — and
          // the next `comfy_queue_prompt` would submit the graph nobody agreed to. Restore and
          // rethrow, so a cancelled edit leaves no trace.
          if (exec.signal.aborted) {
            workspace.graph = snapshot
            throw error
          }
          workspace.revision += 1
          return toJson({
            applied: true,
            rolled_back: false,
            revision: workspace.revision,
            changed: applied,
            validation: { unavailable: renderThrown(error) },
          })
        }

        // Only this node's verdict decides a rollback. A graph can be invalid elsewhere for
        // reasons this edit neither caused nor could fix — a half-built workflow being
        // assembled node by node is the ordinary case — and reverting a correct edit because
        // some other node is still incomplete would make the tool unusable for exactly the
        // task it exists for.
        const nodeVerdict = verdict.node_errors[args.node_id]
        const nodeFailed = nodeVerdict !== undefined && nodeVerdict.errors.length > 0

        if (nodeFailed && args.rollback !== false) {
          workspace.graph = snapshot
          return toJson({
            applied: false,
            rolled_back: true,
            reason: `the mutation left node '${args.node_id}' invalid; the graph was restored`,
            revision: workspace.revision,
            attempted: applied,
            validation: {
              ok: false,
              origin: verdict.origin,
              graph_errors: [],
              node_errors: { [args.node_id]: nodeVerdict },
            },
          })
        }

        workspace.revision += 1
        return toJson({
          applied: true,
          rolled_back: false,
          revision: workspace.revision,
          changed: applied,
          // The whole-graph verdict travels even on success, because the useful question after
          // an edit is usually "is the graph queueable now", not "was that one field legal".
          validation: verdict,
        })
      },
      presentCall: args => ({
        card: 'generic',
        title: `comfy mutate #${args.node_id}${args.input !== undefined ? `.${args.input}` : ''}`,
        kind: 'edit',
        rawInput: args.value === undefined ? (args.set_title ?? '') : JSON.stringify(args.value),
      }),
    }),
  )

  /* --- tool 4: comfy_queue_prompt ------------------------------------------- */

  ctx.tools.register(
    defineTool({
      name: 'comfy_queue_prompt',
      description:
        'Submit the loaded graph to ComfyUI for execution. Returns one of three outcomes and ' +
        'they are not interchangeable: "accepted" (queued, nothing complained about), ' +
        '"accepted_with_dropped_outputs" (queued and running, but some nodes failed ' +
        'validation and the outputs that depended on them will never be produced), or ' +
        '"rejected" (the server refused it and nothing was queued). Read node_errors on the ' +
        'middle outcome; a partial run looks like a success in every other respect. A local ' +
        'pre-check runs first and travels back as local_precheck, but it is advisory and does ' +
        'not stop a submission unless refuse_if_local_invalid is set, in which case the ' +
        'outcome is "not_submitted". This queues work on a single ' +
        'contended GPU shared with every other surface on this machine, so it is not free and ' +
        'should not be called speculatively. Follow progress with comfy_stream_status.',
      parameters: {
        graph: {
          type: 'json',
          description:
            'Submit this graph instead of the session graph. Omit to submit the loaded one.',
        },
        client_id: {
          type: 'string',
          description:
            'Route telemetry to a specific websocket session. Omit to use the bridge\'s own, ' +
            'which is what comfy_stream_status reads.',
        },
        front: {
          type: 'boolean',
          description: 'Queue at the front instead of the back. Ignored if number is given.',
        },
        number: { type: 'integer', description: 'Explicit queue priority. Overrides front.' },
        partial_execution_targets: {
          type: 'array',
          items: { type: 'string' },
          description:
            'Execute only the subgraph feeding these node ids, instead of the whole graph.',
        },
        validate_first: {
          type: 'boolean',
          description:
            'Run the local /object_info check before submitting and report its findings ' +
            'alongside the result. Default true. It is advisory: the graph is submitted ' +
            'either way and the server is the judge. Set false to skip the check entirely.',
        },
        refuse_if_local_invalid: {
          type: 'boolean',
          description:
            'Refuse to submit when the local check finds problems, instead of submitting and ' +
            'letting the server decide. Default false, and leaving it false does NOT risk GPU ' +
            'work on a broken graph: ComfyUI validates before it queues, so an invalid graph ' +
            'costs one rejected HTTP round trip and nothing else. Set it true only if you want ' +
            'the local verdict to be final, accepting that it is the stricter of the two and ' +
            'can refuse a graph ComfyUI would have run.',
        },
        wait: {
          type: 'boolean',
          description:
            'Block until the run finishes and return its outcome. Default false, which ' +
            'returns as soon as it is queued.',
        },
        wait_timeout_ms: {
          type: 'integer',
          description: `How long to wait when wait is true. Maximum ${MAX_FOLLOW_MS}.`,
        },
      },
      output: {
        schema: { type: 'json' },
        render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      // No isConcurrencySafe: this takes the card. `scripts/comfyui.sh` leases the GPU per
      // render, and this tool is a tenant of that lease exactly as a browser visitor is — it
      // deliberately makes no `gpu-governor.sh` call of its own, which would be a second
      // claimant on a mutex it does not own.
      async execute(args, exec: ToolRunContext) {
        const workspace = workspaceFor(exec)
        let graph: ComfyGraph
        if (args.graph !== undefined) {
          const parsed = readGraph(args.graph)
          if (!parsed.ok) throw new Error(`comfy_queue_prompt: ${parsed.detail}`)
          graph = parsed.graph
        } else {
          graph = requireGraph(workspace)
        }

        // The local check is advisory by default, and the asymmetry is the reason.
        //
        // A clean local verdict means "nothing this side can see is wrong", never "this will
        // run" — that principle is written into `validateGraph` and it has a converse this code
        // used to ignore: a dirty local verdict does not mean "this will not run" either. The
        // two directions cost differently. A local false negative just falls through to the
        // server, which is the real judge and answers with the same vocabulary. A local false
        // positive refuses work ComfyUI would have executed, and the caller cannot tell it was
        // this validator and not the engine that said no.
        //
        // That is not a hypothetical: `objectInfo` is cached for 60 s, and every combo input
        // whose permitted values are read off disk — checkpoints, LoRAs, samplers — can be
        // stale against an engine that has just had a file dropped into `models/`. The graph is
        // fine, the cache is old, and the refusal would be ours.
        //
        // And submitting a suspect graph is cheap, which is what settles the default against
        // this repo's "the GPU is a single, contended resource" rule.
        // `references/ComfyUI/server.py:1124-1136` branches on `valid[0]` *before* it queues:
        // the accepted arm calls `self.prompt_queue.put(...)` at `:1131`, the rejected arm
        // returns `status=400` at `:1136` and never reaches the queue. So a graph the server
        // dislikes costs one refused round trip, not a render — there is no GPU work to save by
        // refusing locally, only a round trip, and that is not worth the false positives above.
        //
        // So: run it, attach it, submit anyway. Blocking is opt-in.
        let precheck: GraphVerdict | { unavailable: string } | undefined
        if (args.validate_first !== false) {
          try {
            precheck = validateGraph(graph, await objectInfo(exec.signal))
          } catch (error) {
            if (exec.signal.aborted) throw error
            // An unreadable `/object_info` is not grounds to refuse a submission — the queue
            // endpoint may well answer even when this one did not.
            precheck = { unavailable: renderThrown(error) }
          }
          if ('ok' in precheck && !precheck.ok && args.refuse_if_local_invalid === true) {
            return toJson({
              status: 'not_submitted',
              submitted: false,
              reason:
                'the local /object_info check found problems and refuse_if_local_invalid was ' +
                'set, so nothing was queued. This is a local verdict, not the server\'s: ' +
                'submitting anyway may still succeed.',
              validation: precheck,
            })
          }
        }

        const request: ComfyPromptRequest = { prompt: graph }
        if (args.client_id !== undefined) request.client_id = ClientId(args.client_id)
        if (args.number !== undefined) request.number = args.number
        else if (args.front !== undefined) request.front = args.front
        if (args.partial_execution_targets !== undefined) {
          request.partial_execution_targets = [...args.partial_execution_targets]
        }

        let response: ComfyPromptResponse
        try {
          response = await ctx.comfyui.http.queuePrompt(request, exec.signal)
        } catch (error) {
          if (error instanceof ComfyPromptRejectedError) {
            // Returned, not rethrown. A refused graph is an actionable result the model is
            // expected to read and repair — node_errors names the node and the input — and a
            // thrown error reaches it as a flattened message with that structure destroyed.
            // A transport failure below is different: there is nothing in it to act on.
            return toJson({
              status: 'rejected',
              submitted: false,
              error: error.detail.error,
              validation: {
                ok: false,
                origin: 'server',
                graph_errors: [],
                node_errors: error.detail.node_errors,
              },
              ...(precheck === undefined ? {} : { local_precheck: precheck }),
            })
          }
          // Everything else — transport failure, an unexpected status, a body that is not the
          // documented shape — is rethrown. There is nothing structured in those for a model
          // to repair, which is exactly the distinction that makes returning the rejection
          // above the right call rather than an inconsistency.
          throw error
        }

        // The three-outcome split, and the reason it is not two.
        // `references/ComfyUI/execution.py:1246` ends `validate_prompt` with
        // `return (True, None, list(good_outputs), node_errors)` — accepted, *with*
        // complaints. `server.py:1132` then answers 200 carrying that same `node_errors`. So a
        // prompt can be running right now with some of its outputs already silently dropped,
        // and every entry's `dependent_outputs` (`execution.py:1216-1228`) names exactly which.
        // Folding that into "accepted" would report a partial run as a clean one.
        const failing = Object.entries(response.node_errors)
        const dropped = failing.flatMap(([, record]) => record.dependent_outputs)
        const status = failing.length === 0 ? 'accepted' : 'accepted_with_dropped_outputs'

        const base = {
          status,
          submitted: true,
          prompt_id: response.prompt_id,
          queue_number: response.number,
          dropped_outputs: dropped,
          validation:
            failing.length === 0
              ? { ok: true, origin: 'server', graph_errors: [], node_errors: {} }
              : { ok: false, origin: 'server', graph_errors: [], node_errors: response.node_errors },
          // Carried as its own field, never merged into `validation`. The two are different
          // claims from different authorities and a caller comparing them is the point: a
          // precheck that complained about a graph the server then accepted is this
          // validator's bug, and folding them together would hide it.
          ...(precheck === undefined ? {} : { local_precheck: precheck }),
        }

        if (args.wait !== true) return toJson(base)

        const timeout = Math.min(Math.max(args.wait_timeout_ms ?? 300_000, 1_000), MAX_FOLLOW_MS)
        const outcome = await ctx.comfyui.http.waitForPrompt(response.prompt_id, {
          timeoutMs: timeout,
          signal: exec.signal,
        })
        return toJson({ ...base, outcome })
      },
      presentCall: args => ({
        card: 'generic',
        title: args.wait === true ? 'comfy queue prompt (waiting)' : 'comfy queue prompt',
        kind: 'execute',
      }),
      // No `presentResult`. Returning nothing selects the registry's generic fallback, which
      // renders what `output.render` already produced. A custom result card here would have to
      // reach for the run's status to say anything the fallback does not — and a presenter may
      // only read `(args, value)`, because UIs call it during live streaming *and* during log
      // replay. Closing over the workspace to enrich a card is the exact mistake that makes a
      // replayed transcript show state that did not exist when the call was made.
    }),
  )

  /* --- tool 5: comfy_stream_status ------------------------------------------ */

  ctx.tools.register(
    defineTool({
      name: 'comfy_stream_status',
      description:
        'Read ComfyUI execution telemetry and the current queue. Frames are buffered as they ' +
        'arrive over the engine websocket and replayed here in order; pass since_seq from a ' +
        'previous result to read only what is new. Entries marked kind "gap" are not engine ' +
        'frames: they mark a period when the socket was down and frames were lost. Nothing is ' +
        'synthesised to fill a gap, so after one, read the durable outcome from history ' +
        'rather than inferring it from progress frames. Set wait_ms to park until something ' +
        'new arrives instead of returning an empty list.',
      parameters: {
        prompt_id: {
          type: 'string',
          description: 'Return only frames carrying this prompt id. Gap markers are excluded.',
        },
        since_seq: {
          type: 'integer',
          description:
            'Return only frames after this sequence number. Use next_seq from the previous ' +
            'result. Omit to read from the start of the buffer.',
        },
        limit: {
          type: 'integer',
          description: `Maximum frames to return. Default 50, hard maximum ${FRAME_BUFFER_SIZE}.`,
        },
        wait_ms: {
          type: 'integer',
          description:
            `Park up to this many milliseconds for a new frame if none is available. Maximum ` +
            `${MAX_WAIT_MS}. Default 0, which returns immediately.`,
        },
        include_queue: {
          type: 'boolean',
          description:
            'Also fetch the live queue from GET /queue. Default true. Set false to read only ' +
            'the buffer, with no request to the engine.',
        },
      },
      output: {
        schema: { type: 'json' },
        render: (_args, value) => [{ type: 'text', text: JSON.stringify(value, null, 2) }],
      },
      // Reads the buffer and, optionally, GET /queue. Mutates nothing.
      isConcurrencySafe: () => true,
      async execute(args, exec: ToolRunContext) {
        const limit = Math.min(Math.max(args.limit ?? 50, 1), FRAME_BUFFER_SIZE)
        const since = Math.max(args.since_seq ?? 0, 0)

        let batch = framesSince(since, limit, args.prompt_id)

        if (batch.length === 0 && (args.wait_ms ?? 0) > 0) {
          const budget = Math.min(args.wait_ms ?? 0, MAX_WAIT_MS)
          // `timeoutMs` is NOT declared on this tool and the wait is enforced here instead.
          // `references/deepseek-harness/packages/core/tools/README.md` says under Known
          // Limitations that the registry never enforces deadlines — enforcement needs the
          // `dsh-tool-call-timeout-policy` wrapper. Declaring a budget the registry ignores
          // would be a fabricated guarantee; the timer below is a real one.
          try {
            await abortable<void>(exec.signal, resolve => {
              const timer = setTimeout(resolve, budget)
              const wake = (): void => {
                clearTimeout(timer)
                waiters.delete(wake)
                resolve()
              }
              waiters.add(wake)
              return () => {
                clearTimeout(timer)
                waiters.delete(wake)
              }
            })
          } catch (error) {
            // Cancelled. Rethrow rather than falling through with a partial buffer.
            //
            // The version of this comment that stood here said the registry reads `exec.signal`
            // itself and marks the call aborted, so returning frames anyway was harmless. That
            // is an assumption about the caller, and it is the same assumption that made the
            // aborted-edit bug in `comfy_mutate_node` — a tool that answers a cancelled call
            // hands back a result nobody waited for, and a poller reading `next_seq` out of it
            // would advance its cursor past frames it never saw. Being read-only makes the
            // damage smaller, not the answer honest.
            throw error
          }
          batch = framesSince(since, limit, args.prompt_id)
        }

        const last = batch.at(-1)
        const result: Record<string, unknown> = {
          frames: batch,
          returned: batch.length,
          // `next_seq` is the live sequence when the batch is empty, not 0 — otherwise a
          // caller polling an idle engine would rewind to the start of the buffer and replay
          // everything it had already read.
          next_seq: last?.seq ?? Math.max(since, sequence),
          buffer_size: frames.length,
          buffer_capacity: FRAME_BUFFER_SIZE,
          // True when the caller's cursor has fallen off the back of the ring. Frames between
          // `since_seq` and the oldest surviving frame are gone, and saying so is the only
          // honest answer — the alternative is a caller believing it read a complete stream.
          dropped_before_cursor:
            frames.length > 0 && since > 0 && (frames[0]?.seq ?? 0) > since + 1,
        }

        if (args.include_queue !== false) {
          try {
            result['queue'] = await ctx.comfyui.http.queueState(exec.signal)
          } catch (error) {
            // Cancellation first, for the same reason as everywhere else in this file: a catch
            // that turns a failure into a *field* is a catch that answers a cancelled call.
            // `queue_unavailable` means "the engine did not answer"; an abort means "you told
            // me to stop", and reporting the second as the first would have a caller diagnosing
            // an engine that was fine.
            if (exec.signal.aborted) throw error
            // Reported as its own field rather than thrown: the buffered frames are still
            // valid and useful, and losing them because a second request failed would be a
            // worse answer than an annotated partial one.
            result['queue_unavailable'] = renderThrown(error)
          }
        }

        return toJson(result)
      },
      presentCall: args => ({
        card: 'generic',
        title: 'comfy stream status',
        kind: 'read',
        rawInput: args.prompt_id ?? '',
      }),
    }),
  )
}

/* ------------------------------------------------------------------ small helpers */

/** First line of a description, for a list projection. Never truncated mid-word with an ellipsis. */
function firstLine(text: string): string {
  const line = text.split('\n', 1)[0] ?? ''
  return line.trim()
}

/** A compact account of a loaded graph: what it contains, without reprinting it. */
function summarise(graph: ComfyGraph): Record<string, unknown> {
  const ids = Object.keys(graph)
  const classes = new Map<string, number>()
  for (const node of Object.values(graph)) {
    classes.set(node.class_type, (classes.get(node.class_type) ?? 0) + 1)
  }
  return {
    node_count: ids.length,
    node_ids: ids,
    class_counts: Object.fromEntries([...classes].sort((a, b) => b[1] - a[1])),
  }
}
