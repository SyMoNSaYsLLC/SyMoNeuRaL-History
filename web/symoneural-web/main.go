// SPDX-License-Identifier: LicenseRef-SyMoNeuRaL-Proprietary
//
// SyMoNeuRaL Web -- the first-party HTTP runtime for symoneural.com.
//
// Copyright (c) 2026 SymonSays LLC. All rights reserved.
// SyMoNeuRaL is a subdivision of SymonSays LLC.
// The complete authoritative licence is in /LICENSE at the repository root.
//
// THIRD-PARTY NOTICE. This program is SyMoNeuRaL-authored source that IMPORTS the Caddy
// web server as a library. Caddy is the work of its own authors and is licensed
// Apache-2.0; it is not SyMoNeuRaL's work and nothing here claims otherwise. The
// SyMoNeuRaL licence above covers THIS FILE and the surrounding integration only. Every
// imported module keeps its own licence, and the generated inventory beside the installed
// binary (THIRD_PARTY_NOTICES.md) records each one with its version and licence.
//
// # Why this file exists at all
//
// The runtime contract for this box requires that every first-party service, executable,
// argv identity and process name begin with `symoneural-`. The obvious shortcut -- copying
// or symlinking /usr/bin/caddy to another filename -- is explicitly forbidden and would be
// a false authorship claim: the bytes would still be somebody else's program wearing our
// name, with no provenance and no way to add our own behaviour later.
//
// So this is a real program. It has its own module, its own main(), its own version and
// licence surfaces, and its own build provenance; it delegates request serving to Caddy
// the way any Go program delegates to a library it imports. That is the same mechanism
// `xcaddy` uses to produce custom Caddy distributions, done explicitly and in-tree so the
// dependency graph, the lockfile and the notices are ours to audit.
//
// # What it deliberately does NOT do
//
// It does not fork Caddy, patch it, vendor a modified copy, or re-implement its config
// language. Behaviour parity with the previously running vendor Caddy is a requirement of
// this migration, and the cheapest way to guarantee parity is to run the same engine
// against the same Caddyfile rather than to reimplement it and hope.
package main

import (
	"fmt"
	"os"
	"runtime"
	"runtime/debug"
	"strings"

	caddycmd "github.com/caddyserver/caddy/v2/cmd"

	// Registers the standard Caddy module set: the HTTP server, the Caddyfile adapter,
	// file_server, reverse_proxy, basicauth, encode, TLS management and the rest. Without
	// this blank import the binary would parse a Caddyfile and then have no handlers to
	// run it with -- which fails at load time, not at build time, and therefore only in
	// production.
	_ "github.com/caddyserver/caddy/v2/modules/standard"
)

// Build metadata. Overridden at link time by ops/build-symoneural-web.sh via -ldflags -X.
// Defaults are deliberately the string "unknown" rather than a plausible-looking value: a
// binary built outside the recorded procedure should SAY it has no provenance instead of
// quietly reporting a version somebody will later treat as evidence.
var (
	product      = "SyMoNeuRaL"
	component    = "symoneural-web"
	version      = "unknown"
	gitCommit    = "unknown"
	gitDirty     = "unknown"
	buildID      = "unknown"
	licenseID    = "LicenseRef-SyMoNeuRaL-Proprietary"
	licenseSHA   = "unknown"
	noticesPath  = "unknown"
	licensePath  = "unknown"
	upstreamNote = "embeds github.com/caddyserver/caddy/v2 (Apache-2.0), not authored by SyMoNeuRaL"
)

// caddyVersion reads the Caddy module version out of the binary's own embedded build info
// rather than a constant we would have to remember to update. If the two ever disagree the
// constant is the one that is wrong, so there is no constant.
func caddyVersion() string {
	info, ok := debug.ReadBuildInfo()
	if !ok {
		return "unknown"
	}
	for _, d := range info.Deps {
		if d.Path == "github.com/caddyserver/caddy/v2" {
			if d.Replace != nil {
				return d.Replace.Version + " (replaced)"
			}
			return d.Version
		}
	}
	return "unknown"
}

func printVersion() {
	fmt.Printf("%s %s %s\n", product, component, version)
	fmt.Printf("  component      : %s\n", component)
	fmt.Printf("  version        : %s\n", version)
	fmt.Printf("  git commit     : %s (dirty=%s)\n", gitCommit, gitDirty)
	fmt.Printf("  build id       : %s\n", buildID)
	fmt.Printf("  go             : %s %s/%s\n", runtime.Version(), runtime.GOOS, runtime.GOARCH)
	fmt.Printf("  licence        : %s\n", licenseID)
	fmt.Printf("  licence sha256 : %s\n", licenseSHA)
	fmt.Printf("  licence file   : %s\n", licensePath)
	fmt.Printf("  third-party    : %s\n", noticesPath)
	fmt.Printf("  upstream engine: github.com/caddyserver/caddy/v2 %s (Apache-2.0)\n", caddyVersion())
}

func printLicense() {
	fmt.Printf("%s %s\n\n", product, component)
	fmt.Println("FIRST-PARTY LICENCE")
	fmt.Printf("  %s\n", licenseID)
	fmt.Println("  SyMoNeuRaL Proprietary License")
	fmt.Println("  Copyright (c) 2026 SymonSays LLC. All rights reserved.")
	fmt.Println("  SyMoNeuRaL is a subdivision of SymonSays LLC.")
	fmt.Printf("  Full text : %s\n", licensePath)
	fmt.Printf("  SHA-256   : %s\n", licenseSHA)
	fmt.Println()
	fmt.Println("SCOPE")
	fmt.Println("  The licence above covers SyMoNeuRaL-authored material only. It does NOT")
	fmt.Println("  replace, override or restate the licence of any third-party component.")
	fmt.Println()
	fmt.Println("THIRD-PARTY COMPONENTS")
	fmt.Printf("  This program embeds the Caddy web server, %s, licensed Apache-2.0.\n", caddyVersion())
	fmt.Println("  Caddy is the work of its own authors. SyMoNeuRaL does not claim authorship")
	fmt.Println("  of it, and its copyright notices and licence travel with this binary.")
	fmt.Printf("  Complete inventory: %s\n", noticesPath)
}

// main handles only the two first-party surfaces the runtime contract requires, then hands
// everything else to Caddy unchanged.
//
// The flags are matched exactly and only in argv[1]. A looser match -- scanning the whole
// argv, or accepting a prefix -- would shadow arguments that legitimately belong to Caddy's
// own subcommands, and a web server that silently refuses to start because it thought a
// config path was a flag is a worse failure than a missing convenience.
func main() {
	if len(os.Args) > 1 {
		switch strings.TrimSpace(os.Args[1]) {
		case "--version", "-version":
			printVersion()
			return
		case "--license", "-license", "--licence", "-licence":
			printLicense()
			return
		}
	}
	caddycmd.Main()
}
