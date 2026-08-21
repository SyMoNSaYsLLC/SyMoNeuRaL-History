# oematch

Fingerprint an artifact (`.deb`, `.tar.*`, `.whl`, `.zip`, ELF, or a directory) and rank
OpenEmbedded/Yocto recipes that provide the same libraries, tools and dependencies.

Signals used: dpkg control `Depends`, ELF `DT_NEEDED` (`readelf -d`), printable strings
(`strings`) filtered for URLs / sonames / known tool names, and `requirements.txt`,
`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, wheel `METADATA`, Python/JS imports.
There is no disassembly or decompilation stage — by design.

## Build corpus

```sh
oematch build                     # clone every master-branch layer from layers.openembedded.org (~10 GB)
oematch build --only openembedded-core meta-oe meta-python meta-arm meta-xilinx
oematch add ~/yocto/poky/meta ~/yocto/meta-openembedded/meta-oe   # offline, layers you already have
oematch stats
```

DB lives at `~/.cache/oematch/corpus.db` (override with `--db` or `OEMATCH_DB`).

## Match

```sh
oematch scan  some-tool_1.2.3_amd64.deb          # just the signals, JSON
oematch match some-tool_1.2.3_amd64.deb          # ranked recipes + evidence
oematch match ./vendor-sdk.tar.gz --emit         # + bblayers list and DEPENDS stub
oematch match ./some-binary --json > report.json
```

## Scoring

| evidence                         | pts |
|----------------------------------|-----|
| homepage / SRC_URI host match    | 9   |
| exact PN / PROVIDES / RPROVIDES  | 8   |
| soname → recipe                  | 7   |
| dep name → recipe                | 6   |
| tool name → recipe               | 5   |
| import → python3-*/nodejs-*      | 4   |
| FTS on summary/description       | ≤1  |

High scores with many `soname:`/`dep:` hits = artifact is mostly assembled from things OE already
packages. Low scores with only `fts` = original work; nothing to map.

## Build the .deb

```sh
sudo apt install debhelper dh-python python3-all python3-setuptools pybuild-plugin-pyproject
dpkg-buildpackage -us -uc -b
sudo apt install ../oematch_0.1.0_all.deb
```

## Roadmap

- embeddings over `strings_sample` + recipe descriptions (sqlite-vec, local model) for fuzzy matches
- SWH / GitHub code-search backends for file-hash and string lookups beyond the OE corpus
- `.rpm`, `.ipk`, AppImage (squashfs) extraction
- per-recipe `FILES`/`RPROVIDES` expansion so sonames resolve without the static map
