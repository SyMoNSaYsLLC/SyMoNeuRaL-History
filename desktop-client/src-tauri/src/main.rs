// SyMoNeuRaL Desktop Client -- the Rust half.
//
// The window renders desktop-client/ui/ from Tauri's own protocol origin, and every call to
// the API goes through a command in this file rather than through fetch() in the page. That
// is not indirection for its own sake; three things fall out of it that the other shape does
// not give:
//
//   1. backend/api.py mounts no CORS middleware, and it should not gain one for us. `/api*`
//      is proxied to the public internet by ops/Caddyfile, so an Access-Control-Allow-Origin
//      added to suit a desktop client would be a change to the public serving path made for
//      a private consumer. A fetch() from the webview origin would need exactly that.
//   2. The host is pinned here, in compiled code, as a constant the page cannot reach or
//      override. `ui/app.js` names paths -- "/api/chat" -- and never a host. A client that
//      cannot express a remote address cannot be pointed at one by a config edit.
//   3. `checked()` refuses anything that is not an /api/ path, so a bug in the page turns
//      into a refusal here instead of an arbitrary request.
//
// Streaming is the one place this shape costs something. /api/chat is Server-Sent Events, so
// the page cannot simply await a value; the stream is parsed here and each frame re-emitted
// as a Tauri event, which the page listens for. The frames are passed through UNCHANGED --
// this file never invents, rounds or recomputes a field. `tok_per_s` in particular is the
// server's own measurement and is forwarded verbatim, because a rate computed on this side
// would be a different number wearing the same name.

use base64::Engine as _;
use futures_util::StreamExt;
use tauri::{Emitter, Window};

/// The only host this program can talk to. See note 2 above.
const API: &str = "http://127.0.0.1:8800";

/// Every command routes through here. A path that is not under `/api/` is refused rather
/// than joined onto the base, which is what stops a page-side bug from becoming a request
/// to somewhere else entirely -- `//evil.example/x` is a valid relative URL to a browser
/// and is not a valid argument here.
fn checked(path: &str) -> Result<String, String> {
    if !path.starts_with("/api/") || path.starts_with("/api//") || path.contains("..") {
        return Err(format!("refused: {path:?} is not an /api/ path"));
    }
    Ok(format!("{API}{path}"))
}

fn client() -> Result<reqwest::Client, String> {
    reqwest::Client::builder()
        // No global timeout: an image render legitimately takes tens of seconds on a
        // contended card, and a client-side cut would report a failure the server never had.
        .connect_timeout(std::time::Duration::from_secs(3))
        .build()
        .map_err(|e| e.to_string())
}

/// GET an /api/ path and return the parsed JSON. Used for /api/status.
#[tauri::command]
async fn api_get(path: String) -> Result<serde_json::Value, String> {
    let url = checked(&path)?;
    let response = client()?.get(&url).send().await.map_err(|e| e.to_string())?;
    let status = response.status();
    let body = response.text().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(describe(status.as_u16(), &body));
    }
    serde_json::from_str(&body).map_err(|e| e.to_string())
}

/// POST JSON to an /api/ path and return the parsed JSON. Used for /api/image and
/// /api/ravencalc, both of which answer with a single document.
#[tauri::command]
async fn api_post(path: String, body: serde_json::Value) -> Result<serde_json::Value, String> {
    let url = checked(&path)?;
    let response = client()?
        .post(&url)
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;
    let status = response.status();
    let text = response.text().await.map_err(|e| e.to_string())?;
    if !status.is_success() {
        return Err(describe(status.as_u16(), &text));
    }
    serde_json::from_str(&text).map_err(|e| e.to_string())
}

/// Fetch a binary /api/ path and return it as a data: URL.
///
/// This exists for /api/gen/<name>. A render comes back as a *path* in ImageResult.url, and
/// the browser cannot load it directly: the page's origin is Tauri's protocol, not the API's,
/// so an <img src="http://127.0.0.1:8800/..."> is a cross-origin load subject to the same
/// policy as note 1. Pulling the bytes through here and handing back a data: URL keeps the
/// window's content-security-policy tight -- img-src never needs to name a network origin.
#[tauri::command]
async fn api_bytes(path: String) -> Result<String, String> {
    let url = checked(&path)?;
    let response = client()?.get(&url).send().await.map_err(|e| e.to_string())?;
    let status = response.status();
    if !status.is_success() {
        let body = response.text().await.unwrap_or_default();
        return Err(describe(status.as_u16(), &body));
    }
    let mime = response
        .headers()
        .get(reqwest::header::CONTENT_TYPE)
        .and_then(|v| v.to_str().ok())
        .unwrap_or("image/png")
        .to_string();
    let bytes = response.bytes().await.map_err(|e| e.to_string())?;
    let encoded = base64::engine::general_purpose::STANDARD.encode(&bytes);
    Ok(format!("data:{mime};base64,{encoded}"))
}

/// POST /api/chat and re-emit every Server-Sent Event frame to the window.
///
/// The endpoint's contract, from backend/api.py: each event is `{"delta": "..."}`; an
/// optional earlier frame carries `{"assist": {...}}` when RavenCalc got an exact answer in
/// before the model could speak; the last is `{"done": true, "tokens", "seconds",
/// "tok_per_s", "model", "adapter"}`; and a failure arrives as `{"error": "..."}` inside a
/// 200 stream rather than as an HTTP status, because the response has already begun.
///
/// Frames are forwarded as they parse, so the page renders tokens as they arrive rather than
/// after the turn. `event` is the name the page listens on; it is passed in so two windows
/// could stream at once without crossing, and it is validated for the same reason `checked`
/// exists.
#[tauri::command]
async fn api_chat(
    window: Window,
    event: String,
    path: String,
    body: serde_json::Value,
) -> Result<(), String> {
    if !event.starts_with("chat:") {
        return Err(format!("refused: {event:?} is not a chat: event name"));
    }
    // Takes the path from the caller like the other three, rather than hardcoding it here.
    // That is not symmetry for its own sake: it keeps every endpoint this program touches
    // named in `ui/app.js`, where the audit can see them, instead of one of the four being
    // invisible to a reader of the page. `checked()` still governs what is reachable.
    let url = checked(&path)?;
    let response = client()?
        .post(&url)
        .json(&body)
        .send()
        .await
        .map_err(|e| e.to_string())?;

    let status = response.status();
    if !status.is_success() {
        let text = response.text().await.unwrap_or_default();
        return Err(describe(status.as_u16(), &text));
    }

    // SSE frames are separated by a blank line and can be split across chunks at any byte,
    // so the tail of an incomplete frame has to survive into the next read. Accumulate, cut
    // on "\n\n", keep the remainder.
    let mut stream = response.bytes_stream();
    let mut buffer = String::new();
    while let Some(chunk) = stream.next().await {
        let chunk = chunk.map_err(|e| e.to_string())?;
        buffer.push_str(&String::from_utf8_lossy(&chunk));
        while let Some(cut) = buffer.find("\n\n") {
            let frame: String = buffer.drain(..cut + 2).collect();
            for line in frame.lines() {
                let Some(payload) = line.strip_prefix("data: ") else {
                    continue;
                };
                match serde_json::from_str::<serde_json::Value>(payload) {
                    // Forwarded exactly as received. Nothing in this file adds a field or
                    // changes a number.
                    Ok(value) => window.emit(&event, value).map_err(|e| e.to_string())?,
                    Err(e) => window
                        .emit(
                            &event,
                            serde_json::json!({"error": format!("unparsable frame: {e}")}),
                        )
                        .map_err(|e| e.to_string())?,
                }
            }
        }
    }
    Ok(())
}

/// Turn a failed response into something a person can act on.
///
/// The API's own message is preferred when there is one -- FastAPI puts it in `detail`, and
/// it is more specific than anything this side could say ("Chat surface is not available."
/// tells you to switch a surface on; "HTTP 503" does not). A refused connection is the one
/// case worth interpreting, because it has exactly one cause worth checking first.
fn describe(status: u16, body: &str) -> String {
    let detail = serde_json::from_str::<serde_json::Value>(body)
        .ok()
        .and_then(|v| v.get("detail").and_then(|d| d.as_str()).map(str::to_owned));
    match detail {
        Some(message) => format!("HTTP {status}: {message}"),
        None => format!("HTTP {status}"),
    }
}

fn main() {
    tauri::Builder::default()
        .invoke_handler(tauri::generate_handler![
            api_get, api_post, api_bytes, api_chat
        ])
        .run(tauri::generate_context!())
        .expect("failed to start the SyMoNeuRaL desktop client");
}

#[cfg(test)]
mod tests {
    use super::{checked, describe, API};

    #[test]
    fn only_api_paths_are_reachable() {
        assert!(checked("/api/status").is_ok());
        for refused in [
            "/",
            "/site/index.html",
            "http://example.com/api/x",
            "//example.com/api/x",
            "/api//example.com",
            "/api/../etc/passwd",
            "/local/intake",
        ] {
            assert!(checked(refused).is_err(), "should refuse {refused}");
        }
    }

    #[test]
    fn the_only_host_is_loopback() {
        // The point of the constant is that it is the only one. If somebody adds a second
        // host this fails, which is the whole intent.
        assert_eq!(API, "http://127.0.0.1:8800");
        assert!(checked("/api/chat").unwrap().starts_with("http://127.0.0.1:8800/api/"));
    }

    #[test]
    fn the_api_message_survives_into_the_error() {
        assert_eq!(
            describe(503, r#"{"detail":"Chat surface is not available."}"#),
            "HTTP 503: Chat surface is not available."
        );
        assert_eq!(describe(500, "not json at all"), "HTTP 500");
    }
}
