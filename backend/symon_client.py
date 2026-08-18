#!/usr/bin/env python3
"""Zero-dependency client for a Symon inference server (llama.cpp-compatible) (OpenAI-compatible + native endpoints).

Usage:
    from symon_client import SymonClient
    c = SymonClient("http://localhost:8080")
    print(c.chat([{"role": "user", "content": "hello"}]))

Stdlib only. No pip installs.
"""
import json
import urllib.request


class SymonClient:
    def __init__(self, base_url="http://localhost:8080", api_key=None, timeout=300):
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    # ---------- core HTTP ----------
    def _req(self, method, path, body=None):
        url = f"{self.base}{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            raw = r.read().decode()
            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                return raw

    def _get(self, path):
        return self._req("GET", path)

    def _post(self, path, body):
        return self._req("POST", path, body)

    # ---------- OpenAI-compatible (/v1) ----------
    def models(self):
        return self._get("/v1/models")

    def chat(self, messages, model="default", stream=False, **kw):
        body = {"model": model, "messages": messages, "stream": stream, **kw}
        if stream:
            return self._stream("/v1/chat/completions", body)
        return self._post("/v1/chat/completions", body)

    def completion_v1(self, prompt, model="default", **kw):
        return self._post("/v1/completions", {"model": model, "prompt": prompt, **kw})

    def embeddings(self, input_, model="default", **kw):
        return self._post("/v1/embeddings", {"model": model, "input": input_, **kw})

    def rerank(self, query, documents, model="default", **kw):
        return self._post("/v1/rerank", {"model": model, "query": query, "documents": documents, **kw})

    # ---------- llama.cpp native ----------
    def health(self):
        return self._get("/health")

    def props(self):
        return self._get("/props")

    def set_props(self, **props):
        return self._post("/props", props)

    def completion(self, prompt, **kw):
        """Native /completion — full sampler control (n_predict, temperature, top_k, etc.)."""
        return self._post("/completion", {"prompt": prompt, **kw})

    def tokenize(self, content, add_special=False, with_pieces=False):
        return self._post("/tokenize", {"content": content, "add_special": add_special, "with_pieces": with_pieces})

    def detokenize(self, tokens):
        return self._post("/detokenize", {"tokens": tokens})

    def infill(self, input_prefix, input_suffix, **kw):
        return self._post("/infill", {"input_prefix": input_prefix, "input_suffix": input_suffix, **kw})

    def embedding_native(self, content):
        return self._post("/embedding", {"content": content})

    def slots(self):
        return self._get("/slots")

    def slot_action(self, slot_id, action, filename=None):
        """action: 'save' | 'restore' | 'erase'"""
        body = {"filename": filename} if filename else {}
        return self._post(f"/slots/{slot_id}?action={action}", body)

    def metrics(self):
        return self._get("/metrics")  # Prometheus text format

    def lora_adapters(self):
        return self._get("/lora-adapters")

    def set_lora_adapters(self, adapters):
        """adapters: [{"id": 0, "scale": 1.0}, ...]"""
        return self._post("/lora-adapters", adapters)

    # ---------- streaming (SSE) ----------
    def _stream(self, path, body):
        url = f"{self.base}{path}"
        req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST")
        req.add_header("Content-Type", "application/json")
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            for line in r:
                line = line.decode().strip()
                if not line.startswith("data: "):
                    continue
                chunk = line[6:]
                if chunk == "[DONE]":
                    break
                yield json.loads(chunk)


if __name__ == "__main__":
    import sys
    c = SymonClient(sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8080")
    print("health:", c.health())
    print("models:", json.dumps(c.models(), indent=2))
    r = c.chat([{"role": "user", "content": "Say hi in five words."}])
    print("chat:", r["choices"][0]["message"]["content"])
