#!/usr/bin/env python3
"""Create the four DispatchOS logins and write the passwords where only root can read them.

Task #106. Garrett asked to test *"garrett and ben logins (including test customer level
garrett and ben logins)"* -- two people, two tiers, four accounts.

    sudo python3 tools/dispatchos_accounts.py --seed
    sudo python3 tools/dispatchos_accounts.py --show-path
    sudo python3 tools/dispatchos_accounts.py --reset garrett

## THE PASSWORDS ARE NEVER PRINTED, and that is the whole design of this file

Request ledger R-168, generalised from an incident in this project: **a credential that has
been displayed is spent.** A password echoed into a terminal is in that terminal's
scrollback, in the shell history of whatever produced it, and -- when an agent ran the
command -- in a transcript. So this script generates the values, hands them to the store as
scrypt hashes, and writes the plaintexts to a single root-owned mode-0600 file **outside the
repository**. Nothing goes to stdout except the path and the usernames.

That file is the handover. Read it once, give the passwords to the people who need them the
way you intended to, and delete it:

    sudo cat /etc/symoneural/dispatchos-logins.txt
    sudo shred -u /etc/symoneural/dispatchos-logins.txt

## Why outside the repository

`/etc/symoneural/` is root-owned 0700 and is where `scripts/enable-surfaces.sh` already puts
the API's secrets, for a reason it states plainly: there is no git remote today, but "not
committed" should not depend on remembering. A credentials file inside the tree is one
`git add -A` from being permanent.

## Re-running is safe

`--seed` only creates accounts that are absent, so running it twice does not invalidate a
password somebody has already been given. Use `--reset <username>` to deliberately roll one.
"""
from __future__ import annotations

import argparse
import os
import pathlib
import secrets
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

OUT = pathlib.Path("/etc/symoneural/dispatchos-logins.txt")

#: Four accounts: two people, two tiers. The customer-tier names are suffixed rather than
#: being separate people, because the point is for Garrett and Ben to each SEE the customer
#: view, not to invent two fictional customers whose trips nobody recognises.
ACCOUNTS = [
    ("garrett", "operator"),
    ("ben", "operator"),
    ("garrett-rider", "customer"),
    ("ben-rider", "customer"),
]


def gen() -> str:
    """A password nobody has to type twice but can read aloud once.

    `token_urlsafe` rather than a wordlist: there is no wordlist on this box that is not a
    dependency, and a 24-byte urlsafe token is 192 bits.
    """
    return secrets.token_urlsafe(18)


def write_out(pairs: list[tuple[str, str, str]]) -> None:
    """Write the handover file, 0600, root-owned, replacing whatever was there."""
    OUT.parent.mkdir(parents=True, exist_ok=True)
    os.chmod(OUT.parent, 0o700)
    lines = [
        "# DispatchOS logins. Written by tools/dispatchos_accounts.py.",
        "#",
        "# READ THIS ONCE, HAND THE PASSWORDS OVER, THEN DELETE THE FILE:",
        "#     sudo shred -u %s" % OUT,
        "#",
        "# These are the APPLICATION logins at https://symoneural.com/demo/dispatchos.",
        "# They are NOT the basicauth password on the door -- that is separate and already",
        "# issued (donnie / garrett / ben / dispatchos-preview-test in ops/Caddyfile).",
        "#",
        "# username            role       password",
    ]
    for user, role, pw in pairs:
        lines.append(f"{user:<20}{role:<11}{pw}")
    # Written with a restrictive umask rather than chmod-after-write: between an open(0644)
    # and a chmod there is a window in which the file is world-readable, and the whole point
    # of this file is that there is no such window.
    fd = os.open(str(OUT), os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(OUT, 0o600)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--seed", action="store_true",
                    help="create any of the four accounts that do not exist")
    ap.add_argument("--reset", metavar="USERNAME",
                    help="roll one account's password")
    ap.add_argument("--list", action="store_true", help="usernames and roles, no secrets")
    ap.add_argument("--show-path", action="store_true", help="where the handover file is")
    args = ap.parse_args()

    if args.show_path:
        print(OUT)
        return 0

    # Imported here rather than at module scope so --show-path works without the backend
    # importing cleanly, which is the one thing you want when something is already wrong.
    from apps.dispatchos import store

    store.init_db()

    if args.list:
        for u in store.list_users():
            print(f"{u['username']:<20}{u['role']}")
        return 0

    if args.reset:
        pw = gen()
        try:
            store.set_password(args.reset, pw)
        except store.DispatchError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        role = next((u["role"] for u in store.list_users()
                     if u["username"] == args.reset), "?")
        write_out([(args.reset, role, pw)])
        print(f"rolled {args.reset}. The new password is in {OUT} (mode 0600).")
        return 0

    if not args.seed:
        ap.print_help()
        return 2

    have = {u["username"].lower() for u in store.list_users()}
    pairs: list[tuple[str, str, str]] = []
    for user, role in ACCOUNTS:
        if user.lower() in have:
            print(f"  {user:<20}already exists -- left alone")
            continue
        pw = gen()
        store.create_user(user, pw, role, label={
            "garrett": "Garrett (operator)", "ben": "Ben (operator)",
            "garrett-rider": "Garrett (customer view)",
            "ben-rider": "Ben (customer view)"}[user])
        pairs.append((user, role, pw))
        print(f"  {user:<20}created as {role}")

    if not pairs:
        print("\nNothing to do -- all four accounts already exist. "
              f"Use --reset <username> to roll one.")
        return 0

    write_out(pairs)
    print(f"\n{len(pairs)} password(s) written to {OUT} (root-only, mode 0600).")
    print("They were NOT printed here on purpose: a credential that has been displayed is "
          "spent.")
    print(f"Read them with:  sudo cat {OUT}")
    print(f"Then delete it:  sudo shred -u {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
