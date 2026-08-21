"""SQLite store for the OpenEmbedded corpus. FTS5 over recipe metadata."""
import os
import sqlite3
from pathlib import Path

DEFAULT_DB = Path(os.environ.get("OEMATCH_DB", Path.home() / ".cache/oematch/corpus.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS layers(
  id INTEGER PRIMARY KEY, name TEXT UNIQUE, vcs_url TEXT, branch TEXT,
  subdir TEXT, license TEXT, description TEXT, local_path TEXT
);
CREATE TABLE IF NOT EXISTS recipes(
  id INTEGER PRIMARY KEY, layer_id INTEGER REFERENCES layers(id),
  pn TEXT, pv TEXT, summary TEXT, description TEXT, homepage TEXT,
  license TEXT, src_uri TEXT, depends TEXT, rdepends TEXT,
  provides TEXT, rprovides TEXT, inherits TEXT, filepath TEXT,
  -- 'bb' provides the recipe; 'bbappend' MODIFIES one another layer provides. They
  -- answer different questions and must not be summed: meta-clang carries 0 .bb files
  -- and 20 .bbappend files, so indexing only .bb made an active layer look empty.
  kind TEXT DEFAULT 'bb'
);
CREATE INDEX IF NOT EXISTS recipes_pn ON recipes(pn);
CREATE VIRTUAL TABLE IF NOT EXISTS recipes_fts USING fts5(
  pn, summary, description, homepage, provides, rprovides, src_uri,
  content='recipes', content_rowid='id', tokenize='unicode61'
);
CREATE TRIGGER IF NOT EXISTS recipes_ai AFTER INSERT ON recipes BEGIN
  INSERT INTO recipes_fts(rowid,pn,summary,description,homepage,provides,rprovides,src_uri)
  VALUES (new.id,new.pn,new.summary,new.description,new.homepage,new.provides,new.rprovides,new.src_uri);
END;
CREATE TRIGGER IF NOT EXISTS recipes_ad AFTER DELETE ON recipes BEGIN
  INSERT INTO recipes_fts(recipes_fts,rowid,pn,summary,description,homepage,provides,rprovides,src_uri)
  VALUES ('delete',old.id,old.pn,old.summary,old.description,old.homepage,old.provides,old.rprovides,old.src_uri);
END;
"""


# Columns added after the first release. `CREATE TABLE IF NOT EXISTS` does not add a
# column to a table that already exists, so a corpus built before the column existed
# would keep working and silently lack it.
MIGRATIONS = [("recipes", "kind", "TEXT DEFAULT 'bb'")]


def connect(path: Path = DEFAULT_DB) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    for table, column, decl in MIGRATIONS:
        have = {r[1] for r in con.execute(f"PRAGMA table_info({table})")}
        if column not in have:
            con.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
    con.commit()
    return con


def upsert_layer(con, name, vcs_url="", branch="", subdir="", license="", description="", local_path=""):
    con.execute(
        """INSERT INTO layers(name,vcs_url,branch,subdir,license,description,local_path)
           VALUES(?,?,?,?,?,?,?)
           ON CONFLICT(name) DO UPDATE SET vcs_url=excluded.vcs_url, branch=excluded.branch,
             subdir=excluded.subdir, license=excluded.license, description=excluded.description,
             local_path=excluded.local_path""",
        (name, vcs_url, branch, subdir, license, description, local_path),
    )
    return con.execute("SELECT id FROM layers WHERE name=?", (name,)).fetchone()[0]


def clear_layer_recipes(con, layer_id):
    con.execute("DELETE FROM recipes WHERE layer_id=?", (layer_id,))


def insert_recipe(con, layer_id, r: dict):
    con.execute(
        """INSERT INTO recipes(layer_id,pn,pv,summary,description,homepage,license,src_uri,
           depends,rdepends,provides,rprovides,inherits,filepath,kind)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (layer_id, r.get("pn", ""), r.get("pv", ""), r.get("summary", ""), r.get("description", ""),
         r.get("homepage", ""), r.get("license", ""), r.get("src_uri", ""), r.get("depends", ""),
         r.get("rdepends", ""), r.get("provides", ""), r.get("rprovides", ""), r.get("inherits", ""),
         r.get("filepath", ""), r.get("kind", "bb")),
    )
