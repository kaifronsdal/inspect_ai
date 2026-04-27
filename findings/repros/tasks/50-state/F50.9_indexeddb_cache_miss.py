#!/usr/bin/env python3
"""F50.9 — IndexedDB cache key mismatch (read absolute, write relative).

THE CLAIM (findings/50-state-and-routing.md § F50.9)
====================================================
``logSlice.ts syncLog()`` computes ``logAbsPath = join(logFileName, logDir)``
and uses it for the **cache-hit read** branch, but the **cache-miss write**
branch writes under raw ``logFileName``.  If ``logFileName`` is relative
(claimed to be "the common case from URL routing") the two keys differ and
the IndexedDB ``log_details`` cache never hits.

WHAT THIS SCRIPT DOES
=====================
1. Cold-deep-links to ``#/logs/<bare-filename>/samples`` (the routing case the
   finding cites) and lets ``App.tsx → loadLog(selectedLogFile) → syncLog()``
   run.
2. Reads back, via ``page.evaluate()``:
     • the key actually written to the ``log_details`` IndexedDB store,
     • ``state.logs.logDir`` and ``state.logs.selectedLogFile`` from Zustand,
     • re-implements ``isUri()`` / ``join()`` from ``utils/uri.ts`` and
       computes what ``syncLog`` would use as ``logAbsPath`` on the **next**
       call.
3. Compares write-key vs read-key.  If they differ → CONFIRMED.
4. As a second channel, hash-reloads the same log and counts the rows in
   ``log_details`` — two rows under different keys would prove the duplicate-
   entry claim.

VERDICT (spoiler — see findings/repros/tasks/50-state/README.md)
================================================================
**FALSE_POSITIVE** in practice for the ``inspect view`` browser path.
The source asymmetry is real, but it is masked one frame upstream:
``logsActions.setSelectedLogFile`` (``logsSlice.ts:382-385``) does
``isUri(logFile) ? logFile : join(logFile, state.logs.logDir)`` **before**
storing ``selectedLogFile``, and the only caller of ``syncLog`` is
``App.tsx:105 loadLog(selectedLogFile)`` — so ``logFileName`` arriving at
``syncLog`` is always already an absolute URI, ``isUri(logFileName)`` is
true, and ``logAbsPath === logFileName``.  The bug is **latent**: it would
fire if any future caller invoked ``syncLog`` with a relative path, or if
``setSelectedLogFile`` ran while ``state.logs.logDir`` was still
``undefined`` (race) — neither of which occurs today.

Run::

    cd ~/GitHub/inspect_ai
    uv run --with playwright python \
        findings/repros/tasks/50-state/F50.9_indexeddb_cache_miss.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "findings" / "repros" / "verify"))

from harness import ViewerSession  # noqa: E402

PORT = 7872
LOG_DIR = REPO / "findings" / "repros" / "logs" / "50-state"

DEVTOOLS_SHIM = """
window.__REDUX_DEVTOOLS_EXTENSION__ = {
  connect: () => ({
    init:  (s)      => { window.__zustate = s; },
    send:  (_a, s)  => { window.__zustate = s; },
    subscribe: () => () => {},
    unsubscribe: () => {},
    error: () => {},
  }),
};
"""

# JS that reproduces utils/uri.ts isUri() + join() and reads IndexedDB.
PROBE_JS = r"""
async () => {
  const s = window.__zustate || {};

  // ---- utils/uri.ts re-impl (verbatim semantics) -----------------------
  const isUri = (v) => { if (!v) return false; try { new URL(v); return true; } catch { return false; } };
  const join = (file, dir) => {
    if (!dir) return file;
    const f = file.replace(/\\/g, "/");
    const d = dir.replace(/\\/g, "/");
    const ds = d.endsWith("/") ? d : d + "/";
    if (f.startsWith(ds)) return f;
    return ds + f;
  };

  // ---- what syncLog() will use on its NEXT call -----------------------
  const logFileName = s.logs?.selectedLogFile;          // arg passed to syncLog
  const logDir      = s.logs?.logDir;
  const logAbsPath  = logFileName && !isUri(logFileName)
                        ? join(logFileName, logDir)
                        : logFileName;

  // ---- what syncLog() actually WROTE on its LAST call -----------------
  const dbs = await indexedDB.databases();
  let writtenKeys = [];
  let dbNames = [];
  for (const d of dbs) {
    if (!d.name || !d.name.startsWith("InspectAI_")) continue;
    dbNames.push(d.name);
    await new Promise((res) => {
      const rq = indexedDB.open(d.name);
      rq.onsuccess = () => {
        const db = rq.result;
        if (!db.objectStoreNames.contains("log_details")) { db.close(); res(); return; }
        const kr = db.transaction("log_details", "readonly")
                     .objectStore("log_details").getAllKeys();
        kr.onsuccess = () => { writtenKeys = writtenKeys.concat(kr.result); db.close(); res(); };
        kr.onerror   = () => { db.close(); res(); };
      };
      rq.onerror = () => res();
    });
  }

  return {
    logDir, logFileName, logAbsPath,
    logFileName_isUri: isUri(logFileName),
    writtenKeys, dbNames,
    loadedLog: s.log?.loadedLog,
  };
}
"""


def main() -> int:
    with ViewerSession(LOG_DIR, port=PORT) as v:
        v.page.add_init_script(DEVTOOLS_SHIM)
        log = v.find_log("F50.3")  # any .eval in 50-state will do

        # ---- 1. Cold deep-link with the BARE filename in the hash -------
        # (this is the "relative logFileName from URL routing" case the
        #  finding cites). goto_log() builds #/logs/<enc filename>/samples.
        v.goto_log(log, tab="samples")
        v.page.wait_for_timeout(2500)  # allow setTimeout(0) IndexedDB write

        first = v.page.evaluate(PROBE_JS)

        # ---- 2. Hash-reload the same log (no full page reload) ----------
        # Forces a second syncLog() — if keys mismatched, a second row would
        # appear under the other key.
        v.page.evaluate("(h) => { window.location.hash = '#/logs'; }", "")
        v.wait_settled()
        v.page.evaluate(
            "(h) => { window.location.hash = h; }",
            f"#/logs/{v._enc(log)}/samples",
        )
        v.wait_settled()
        v.page.wait_for_timeout(2000)
        second = v.page.evaluate(PROBE_JS)

    # ---- analysis -------------------------------------------------------
    write_key = first["writtenKeys"][0] if first["writtenKeys"] else None
    read_key = first["logAbsPath"]
    keys_match = write_key == read_key
    grew = len(set(second["writtenKeys"])) > len(set(first["writtenKeys"]))

    bar = "=" * 72
    print(f"\n{bar}\nF50.9 — IndexedDB cache key: write vs read\n{bar}")
    print(f"  hash route used         : #/logs/{log}/samples  (bare filename)")
    print(f"  state.logs.logDir       : {first['logDir']}")
    print(f"  selectedLogFile         : {first['logFileName']}")
    print(f"  → isUri(selectedLogFile): {first['logFileName_isUri']}")
    print(f"  logAbsPath (read key)   : {read_key}")
    print(f"  log_details write key   : {write_key}")
    print(f"  IndexedDB(s)            : {first['dbNames']}")
    print(f"  rows after 1st load     : {len(first['writtenKeys'])}  {first['writtenKeys']}")
    print(f"  rows after 2nd load     : {len(second['writtenKeys'])}  {second['writtenKeys']}")
    print()

    if write_key is None:
        verdict = "INCONCLUSIVE"
        notes = (
            "No log_details row was written — IndexedDB cache path not\n"
            "    exercised (databaseService not opened?). The asymmetry in\n"
            "    syncLog() cannot be observed without the DB."
        )
    elif not keys_match or grew:
        verdict = "CONFIRMED"
        notes = (
            f"write key ({write_key!r}) ≠ read key ({read_key!r}); cache\n"
            f"    will never hit. Duplicate row appeared on reload: {grew}."
        )
    else:
        verdict = "FALSE_POSITIVE"
        notes = (
            "Read key == write key. The source-level asymmetry in\n"
            "    logSlice.ts:195-247 (read via logAbsPath, write via\n"
            "    logFileName) is real but UNREACHABLE: the only caller is\n"
            "    App.tsx:105 `loadLog(selectedLogFile)`, and\n"
            "    logsSlice.ts:382-385 `setSelectedLogFile` already resolves\n"
            "    `selectedLogFile` to an absolute URI via the same\n"
            "    isUri()/join() before syncLog ever sees it — so inside\n"
            "    syncLog, isUri(logFileName) is always true and\n"
            "    logAbsPath === logFileName. The bug is LATENT (would fire\n"
            "    if a future caller passed a relative path, or if\n"
            "    setSelectedLogFile raced ahead of initLogDir). Recommend\n"
            "    fixing the asymmetry for hygiene but downgrading to INFO."
        )

    print(f"  VERDICT: {verdict}")
    print(f"    {notes}")
    print(bar)
    print(json.dumps({"verdict": verdict, "read_key": read_key, "write_key": write_key}))
    return 0 if verdict != "INCONCLUSIVE" else 1


if __name__ == "__main__":
    sys.exit(main())
