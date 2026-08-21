import argparse
import json
import sys
from pathlib import Path

from . import __version__, db


def cmd_build(a):
    from . import corpus
    corpus.build(Path(a.root), a.branch, set(a.only) if a.only else None, Path(a.db), a.no_fetch)


def cmd_add(a):
    from . import corpus
    corpus.add_local(a.paths, Path(a.db))


def cmd_scan(a):
    from . import extract
    sig = extract.fingerprint(a.target)
    print(sig.to_json())


def cmd_match(a):
    from . import extract, match
    sig = extract.fingerprint(a.target)
    con = db.connect(Path(a.db))
    n = con.execute("SELECT count(*) FROM recipes").fetchone()[0]
    if n == 0:
        sys.exit("corpus empty — run `oematch build` or `oematch add <layer-dir>...` first")
    res = match.Matcher(con).run(sig)
    if a.json:
        print(json.dumps({"signals": json.loads(sig.to_json()), "matches": res}, indent=2))
        return
    print(f"# {sig.source}  [{sig.kind}]  sonames={len(sig.sonames)} deps={len(sig.pkg_deps)} "
          f"imports={len(sig.imports)} tools={len(sig.tools)} urls={len(sig.urls)}\n")
    print(f"{'score':>5}  {'pn':28s} {'layer':22s} {'lic':8s} evidence")
    for r in res[: a.top]:
        ev = ", ".join(r["evidence"][:4])
        print(f"{r['score']:5.1f}  {r['pn'][:28]:28s} {r['layer'][:22]:22s} {r['layer_license'][:8]:8s} {ev}")
    if a.emit:
        print("\n" + match.emit_yocto(res))


def cmd_upstream(a):
    """Which layer carries this upstream project? Answers a URL, not a file.

    With no arguments it walks the curated `UPSTREAM_GROUPS` table and reports the
    resolution rate against it, which is the one number that says whether this command
    works. A rate is printed rather than a pass/fail because a miss here is usually a
    real gap in the corpus -- no layer carries the project -- and that is an answer.
    """
    from . import upstream
    con = db.connect(Path(a.db))
    if con.execute("SELECT count(*) FROM recipes").fetchone()[0] == 0:
        sys.exit("corpus empty — run `oematch build` or `oematch add <layer-dir>...` first")

    rows = [(g, u) for g, u, _ in upstream.UPSTREAM_GROUPS] if not a.urls \
        else [(None, u) for u in a.urls]

    if a.json:
        print(json.dumps([{"url": u, "expected_group": g,
                           "matches": upstream.resolve(con, u, a.top)}
                          for g, u in rows], indent=2))
        return

    ok = wrong = none = 0
    for expect, url in rows:
        res = upstream.resolve(con, url, a.top)
        print(f"\n# {url}" + (f"   [expected: {expect}]" if expect else ""))
        if not res:
            print("    no layer carries this project")
            none += 1
            continue
        for r in res:
            mark = "*" if r["exact_pn"] else " "
            print(f"  {mark} {r['pn']:26s} {r['pv'][:10]:10s} {r['layer']:22s} "
                  f"{r['recipe_license'] or '-':18s} {r['why']}")
        if expect is not None:
            want = upstream.GROUP_LAYERS.get(expect, {expect})
            if any(r["layer"] in want for r in res):
                ok += 1
            else:
                wrong += 1
                print(f"    ^ expected a recipe in {expect}, none of the above is")
    if rows and rows[0][0] is not None:
        print(f"\n{ok} in the expected group, {wrong} resolved elsewhere, "
              f"{none} unresolved, of {len(rows)}")


def cmd_stats(a):
    con = db.connect(Path(a.db))
    for r in con.execute("SELECT l.name, l.license, count(r.id) n FROM layers l LEFT JOIN recipes r ON r.layer_id=l.id GROUP BY l.id ORDER BY n DESC"):
        print(f"{r['n']:6d}  {r['license']:10s} {r['name']}")


def main(argv=None):
    p = argparse.ArgumentParser(prog="oematch", description="Match an artifact to OpenEmbedded layers/recipes.")
    p.add_argument("--db", default=str(db.DEFAULT_DB))
    p.add_argument("-V", "--version", action="version", version=__version__)
    sp = p.add_subparsers(dest="cmd", required=True)

    b = sp.add_parser("build", help="pull every layer from the OE Layer Index and index it")
    b.add_argument("--root", default=str(Path.home() / ".cache/oematch/layers"))
    b.add_argument("--branch", default="master")
    b.add_argument("--only", nargs="*", help="layer names to restrict to")
    b.add_argument("--no-fetch", action="store_true", help="re-index existing clones only")
    b.set_defaults(fn=cmd_build)

    ad = sp.add_parser("add", help="index local layer checkouts (offline)")
    ad.add_argument("paths", nargs="+")
    ad.set_defaults(fn=cmd_add)

    s = sp.add_parser("scan", help="print extracted signals as JSON")
    s.add_argument("target")
    s.set_defaults(fn=cmd_scan)

    m = sp.add_parser("match", help="fingerprint an artifact and rank OE recipes")
    m.add_argument("target")
    m.add_argument("--top", type=int, default=40)
    m.add_argument("--json", action="store_true")
    m.add_argument("--emit", action="store_true", help="append bblayers + DEPENDS stub")
    m.set_defaults(fn=cmd_match)

    up = sp.add_parser("upstream", help="which layer carries this upstream repo URL?")
    up.add_argument("urls", nargs="*", help="repo URLs; empty means the curated set")
    up.add_argument("--top", type=int, default=6)
    up.add_argument("--json", action="store_true")
    up.set_defaults(fn=cmd_upstream)

    st = sp.add_parser("stats", help="corpus summary")
    st.set_defaults(fn=cmd_stats)

    a = p.parse_args(argv)
    a.fn(a)


if __name__ == "__main__":
    main()
