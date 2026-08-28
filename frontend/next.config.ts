import type { NextConfig } from "next";

/**
 * The one thing in this file that can break the live API, so it is the thing that is
 * explained.
 *
 * FastAPI is the authoritative backend and owns every `/api/*` path. Next.js must never
 * answer one. Two rules keep that true and they have to hold together:
 *
 *   1. There is no `src/app/api/` directory in this project, and there must never be one.
 *      An App Router route handler there would shadow the rewrite below silently -- Next
 *      matches its own filesystem routes before it consults `rewrites()`.
 *   2. `/api/:path*` is rewritten to the FastAPI upstream, verbatim. No path rewriting, no
 *      prefix stripping: `/api/dispatchos/board` arrives at FastAPI as `/api/dispatchos/board`.
 *
 * `frontend/tests/route-ownership.test.mjs` asserts both -- the absence of the directory as
 * well as the passthrough -- because rule 1 is the kind of thing a later feature adds without
 * noticing what it took away.
 *
 * The upstream is an environment variable rather than a literal because the port is a
 * deployment fact, not a source fact. The default is the port `ops/Caddyfile` and
 * `symoneural-api.service` already use, so an unset variable behaves like this box.
 */
const API_UPSTREAM = process.env.SYMONEURAL_API_UPSTREAM ?? "http://127.0.0.1:8800";

const nextConfig: NextConfig = {
  reactStrictMode: true,

  // The header names the framework and version to every visitor and buys nothing.
  poweredByHeader: false,

  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_UPSTREAM}/api/:path*` }];
  },
};

export default nextConfig;
