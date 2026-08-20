SUMMARY = "The edge: TLS termination, the Rust gateway, and nothing that routes"
DESCRIPTION = "CLAUDE.md's rule is that FastAPI does all the routing and the web server \
terminates TLS and hands back static files. This group installs exactly the pieces that \
rule allows and no reverse-proxy toolkit that would invite breaking it."
LICENSE = "MIT"
LIC_FILES_CHKSUM = "file://${COMMON_LICENSE_DIR}/MIT;md5=0835ade698e0bcf8506ecda2f7b4f302"

inherit packagegroup

# Caddy rather than Apache, and the reason is load-bearing rather than taste: Caddy
# upgrades WebSockets with no directive at all. Under Apache mod_proxy_wstunnel was never
# enabled, so the rack's "pushed live over one socket" claim had been silently falling
# back to polling -- a config difference that made a published claim untrue.
RDEPENDS:${PN} = "\
    caddy \
    ca-certificates \
    openssl \
    curl \
"

# No nginx, no apache2, no haproxy. Installing a second thing that can route is how the
# routing rule gets broken by someone who did not read it.
