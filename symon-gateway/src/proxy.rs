//! The proxy handlers.
//!
//! Both of them stream. `Body::from_stream` over `reqwest`'s byte stream means a frame leaves
//! for the client as soon as it arrives from upstream, which is the whole point on
//! `/v1/chat/completions` — the site's argument is that you watch tokens land, and a gateway
//! that collects the response before forwarding it turns a stream into a long pause followed
//! by a wall of text. It matters on `/api/*` too: `/api/image` returns a large PNG and
//! `/api/ws` is a socket.

use axum::body::Body;
use axum::extract::{Request, State};
use axum::http::{header, HeaderMap, HeaderName, HeaderValue, StatusCode, Uri};
use axum::response::{IntoResponse, Response};
use futures_util::TryStreamExt;

use crate::error::AppError;
use crate::models::{ChatRequest, Health};
use crate::AppState;

/// Headers that describe *this* connection rather than the message, and must not be copied
/// onto the next hop. RFC 9110 §7.6.1. Forwarding `transfer-encoding` in particular produces
/// a response that is chunked-encoded twice and that no client can decode.
const HOP_BY_HOP: [HeaderName; 8] = [
    header::CONNECTION,
    header::PROXY_AUTHENTICATE,
    header::PROXY_AUTHORIZATION,
    header::TE,
    header::TRAILER,
    header::TRANSFER_ENCODING,
    header::UPGRADE,
    HeaderName::from_static("keep-alive"),
];

fn is_hop_by_hop(name: &HeaderName) -> bool {
    HOP_BY_HOP.iter().any(|h| h == name)
}

/// `GET /healthz` — this process, not the stack.
///
/// It deliberately does **not** poll the upstream. A health check that fails because
/// something else is down cannot be used to tell the two apart, and systemd would restart the
/// wrong unit.
#[utoipa::path(
    get, path = "/healthz", tag = "gateway",
    responses((status = 200, description = "The gateway process is serving", body = Health))
)]
pub async fn healthz(State(st): State<AppState>) -> Response {
    axum::Json(Health {
        status: "ok".into(),
        version: env!("CARGO_PKG_VERSION").into(),
        api_upstream: st.cfg.api_upstream.clone(),
        engine_upstream: st.cfg.engine_upstream.clone(),
        validator: st.validator.kind().into(),
        max_tokens: st.cfg.max_tokens,
    })
    .into_response()
}

/// `ANY /api/*` — forwarded verbatim to the FastAPI control plane.
///
/// Verbatim is the contract. `.claude/CLAUDE.md` states that FastAPI does all the routing, and
/// this handler is what keeps that true with a new process in the path: it makes no routing
/// decision, rewrites no path, and reads no body. It only says *which process owns the URL*.
#[utoipa::path(
    get, path = "/api/{path}", tag = "proxy",
    params(("path" = String, Path, description = "Any path under /api, forwarded unchanged")),
    responses(
        (status = 200, description = "Whatever backend/api.py returned, streamed"),
        (status = 502, description = "backend/api.py did not answer")
    )
)]
pub async fn proxy_api(State(st): State<AppState>, req: Request) -> Result<Response, AppError> {
    let upstream = st.cfg.api_upstream.clone();
    forward(st, &upstream, req).await
}

/// `ANY /v1/*` other than chat completions — models, embeddings, tokenize — forwarded to the
/// engine upstream without validation, because there is no chat payload in them to measure.
#[utoipa::path(
    get, path = "/v1/{path}", tag = "inference",
    params(("path" = String, Path, description = "Any other OpenAI-compatible path")),
    responses(
        (status = 200, description = "Whatever the engine upstream returned, streamed"),
        (status = 502, description = "The engine upstream did not answer")
    )
)]
pub async fn proxy_v1(State(st): State<AppState>, req: Request) -> Result<Response, AppError> {
    let upstream = st.cfg.engine_upstream.clone();
    forward(st, &upstream, req).await
}

/// The single forwarding path used by every proxied route.
pub async fn forward(st: AppState, upstream: &str, req: Request) -> Result<Response, AppError> {
    let (parts, body) = req.into_parts();

    // Path *and* query. Dropping the query string here would silently break `/api/gen/{name}`
    // cache-busting and every paginated route.
    let path_and_query = parts
        .uri
        .path_and_query()
        .map(|p| p.as_str())
        .unwrap_or(parts.uri.path());

    let target: Uri = format!("{upstream}{path_and_query}")
        .parse()
        .map_err(|e| AppError::BadRequest(format!("cannot build upstream URI: {e}")))?;

    let bytes = axum::body::to_bytes(body, usize::MAX)
        .await
        .map_err(|e| AppError::BadRequest(format!("could not read request body: {e}")))?;

    let mut headers = HeaderMap::new();
    for (name, value) in parts.headers.iter() {
        // `host` is dropped rather than forwarded: reqwest sets it from the target URI, and
        // sending the public hostname to 127.0.0.1 makes upstream logs claim a connection that
        // did not happen.
        if is_hop_by_hop(name) || name == header::HOST {
            continue;
        }
        headers.insert(name.clone(), value.clone());
    }
    forwarded_for(&mut headers, &parts.headers);

    let resp = st
        .http
        .request(parts.method.clone(), target.to_string())
        .headers(headers)
        .body(bytes)
        .send()
        .await
        .map_err(|e| {
            AppError::UpstreamUnreachable(format!("{upstream}{path_and_query}: {e}"))
        })?;

    let status = StatusCode::from_u16(resp.status().as_u16())
        .unwrap_or(StatusCode::BAD_GATEWAY);

    let mut out = Response::builder().status(status);
    if let Some(h) = out.headers_mut() {
        for (name, value) in resp.headers().iter() {
            if is_hop_by_hop(name) {
                continue;
            }
            h.append(name.clone(), value.clone());
        }
        // Nginx and friends buffer `text/event-stream` by default and there is no way for the
        // client to tell a buffered stream from a slow model. Caddy honours this header too.
        if !h.contains_key("x-accel-buffering") {
            h.insert("x-accel-buffering", HeaderValue::from_static("no"));
        }
    }

    let stream = resp.bytes_stream().map_err(std::io::Error::other);
    Ok(out
        .body(Body::from_stream(stream))
        .map_err(|e| AppError::Middleware(e.to_string()))?)
}

/// Append this hop to `X-Forwarded-For` rather than replacing it, so the chain survives
/// Caddy -> gateway -> API and the API can still see the real client.
fn forwarded_for(out: &mut HeaderMap, incoming: &HeaderMap) {
    if let Some(existing) = incoming.get("x-forwarded-for") {
        out.insert("x-forwarded-for", existing.clone());
    }
}

/// `POST /v1/chat/completions` — validate the payload, then forward it to the engine upstream.
///
/// The order is the point: validate, *then* forward. A payload over the ceiling is refused
/// here and never reaches anything that would take the GPU lock for it.
#[utoipa::path(
    post, path = "/v1/chat/completions", tag = "inference",
    request_body = ChatRequest,
    responses(
        (status = 200, description = "Completion, as SSE frames when `stream` is true"),
        (status = 413, description = "Rejected by the validator before reaching the engine"),
        (status = 502, description = "The engine upstream did not answer")
    )
)]
pub async fn chat_completions(
    State(st): State<AppState>,
    req: Request,
) -> Result<Response, AppError> {
    let (parts, body) = req.into_parts();

    let bytes = axum::body::to_bytes(body, usize::MAX)
        .await
        .map_err(|e| AppError::BadRequest(format!("could not read request body: {e}")))?;

    // Parsed only to fail fast on a malformed body and to name the model in the log. The
    // *forwarded* bytes are the originals — re-serialising from `ChatRequest` would quietly
    // reorder keys and drop anything `#[serde(flatten)]` could not represent.
    let parsed: ChatRequest = serde_json::from_slice(&bytes)
        .map_err(|e| AppError::BadRequest(format!("not a chat completion request: {e}")))?;

    let tokens = st.validator.check(&bytes).await?;

    tracing::info!(
        component = "gateway",
        model = parsed.model.as_deref().unwrap_or("default"),
        stream = parsed.stream,
        est_tokens = tokens,
        "chat completion accepted"
    );

    let upstream = st.cfg.engine_upstream.clone();
    forward(st, &upstream, Request::from_parts(parts, Body::from(bytes))).await
}
