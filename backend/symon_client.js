// Zero-dependency client for a Symon inference server (llama.cpp-compatible) (OpenAI-compatible + native endpoints).
// Works in Node 18+ (built-in fetch) and browsers. No npm installs.
//
// Usage:
//   import { SymonClient } from "./symon_client.js";
//   const c = new SymonClient("http://localhost:8080");
//   const r = await c.chat([{ role: "user", content: "hello" }]);

export class SymonClient {
  constructor(baseUrl = "http://localhost:8080", apiKey = null) {
    this.base = baseUrl.replace(/\/+$/, "");
    this.apiKey = apiKey;
  }

  // ---------- core HTTP ----------
  async _req(method, path, body) {
    const headers = { "Content-Type": "application/json" };
    if (this.apiKey) headers.Authorization = `Bearer ${this.apiKey}`;
    const res = await fetch(`${this.base}${path}`, {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) throw new Error(`${method} ${path} -> ${res.status}: ${await res.text()}`);
    const text = await res.text();
    try { return JSON.parse(text); } catch { return text; }
  }
  _get(path)        { return this._req("GET", path); }
  _post(path, body) { return this._req("POST", path, body); }

  // ---------- OpenAI-compatible (/v1) ----------
  models() { return this._get("/v1/models"); }

  chat(messages, { model = "default", stream = false, ...kw } = {}) {
    const body = { model, messages, stream, ...kw };
    return stream ? this._stream("/v1/chat/completions", body)
                  : this._post("/v1/chat/completions", body);
  }

  completionV1(prompt, { model = "default", ...kw } = {}) {
    return this._post("/v1/completions", { model, prompt, ...kw });
  }

  embeddings(input, { model = "default", ...kw } = {}) {
    return this._post("/v1/embeddings", { model, input, ...kw });
  }

  rerank(query, documents, { model = "default", ...kw } = {}) {
    return this._post("/v1/rerank", { model, query, documents, ...kw });
  }

  // ---------- llama.cpp native ----------
  health()  { return this._get("/health"); }
  props()   { return this._get("/props"); }
  setProps(props) { return this._post("/props", props); }

  // Native /completion — full sampler control (n_predict, temperature, top_k, ...)
  completion(prompt, kw = {}) { return this._post("/completion", { prompt, ...kw }); }

  tokenize(content, { addSpecial = false, withPieces = false } = {}) {
    return this._post("/tokenize", { content, add_special: addSpecial, with_pieces: withPieces });
  }
  detokenize(tokens) { return this._post("/detokenize", { tokens }); }

  infill(inputPrefix, inputSuffix, kw = {}) {
    return this._post("/infill", { input_prefix: inputPrefix, input_suffix: inputSuffix, ...kw });
  }

  embeddingNative(content) { return this._post("/embedding", { content }); }

  slots() { return this._get("/slots"); }
  slotAction(slotId, action, filename) {
    // action: 'save' | 'restore' | 'erase'
    return this._post(`/slots/${slotId}?action=${action}`, filename ? { filename } : {});
  }

  metrics()      { return this._get("/metrics"); }        // Prometheus text
  loraAdapters() { return this._get("/lora-adapters"); }
  setLoraAdapters(adapters) { return this._post("/lora-adapters", adapters); } // [{id, scale}]

  // ---------- streaming (SSE) ----------
  async *_stream(path, body) {
    const headers = { "Content-Type": "application/json" };
    if (this.apiKey) headers.Authorization = `Bearer ${this.apiKey}`;
    const res = await fetch(`${this.base}${path}`, {
      method: "POST", headers, body: JSON.stringify(body),
    });
    if (!res.ok) throw new Error(`stream ${path} -> ${res.status}`);
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop();
      for (const line of lines) {
        const t = line.trim();
        if (!t.startsWith("data: ")) continue;
        const chunk = t.slice(6);
        if (chunk === "[DONE]") return;
        yield JSON.parse(chunk);
      }
    }
  }
}

// Quick self-test: node symon_client.js [baseUrl]
if (import.meta.url === `file://${process.argv[1]}`) {
  const c = new SymonClient(process.argv[2] || "http://localhost:8080");
  console.log("health:", await c.health());
  console.log("models:", JSON.stringify(await c.models(), null, 2));
  const r = await c.chat([{ role: "user", content: "Say hi in five words." }]);
  console.log("chat:", r.choices[0].message.content);
}
