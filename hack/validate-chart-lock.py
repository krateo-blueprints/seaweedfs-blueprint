#!/usr/bin/env python3
"""Every upstream chart this repository builds from is pinned: the dependency set by Chart.lock, the bytes by digest.

    hack/validate-chart-lock.py [repo-root] [--live]

A dependency resolved from a registry at release time is whatever the registry serves then. Two pins make that the
bytes this repository was reviewed and gated against:

  - Chart.lock, committed. release-tag.yaml runs `helm dependency build`, which refuses a lock that is out of sync with
    Chart.yaml, and never re-resolves. (`helm dependency update` would rewrite the lock silently.)
  - krateo.io/upstream-digest on each chart that names an upstream chart (krateo.io/upstream-chart and
    krateo.io/upstream-version): for an oci:// chart, the OCI manifest digest the registry served for that version
    when it was pinned; for an https:// chart repository, the SHA-256 of the chart archive (its index.yaml digest). A
    version re-published upstream serves other bytes, and the release refuses it.

Offline (always):
  1. every chart with dependencies has a Chart.lock whose dependencies equal Chart.yaml's (name, repository, version),
     and whose digest is the one helm computes from the two lists (sha256 of the JSON of [Chart.yaml deps, lock deps],
     helm's resolver.HashReq), so a hand-edited or stale lock fails here without a network;
  2. every chart naming an upstream chart carries a well-formed krateo.io/upstream-digest; a chart whose dependency is
     that upstream chart names it consistently (same reference and version).
Live (--live; lint and the release run it):
  3. `helm dependency build` succeeds on a copy of each chart with dependencies (helm's own lock check, and the
     dependency exists). An https:// repository is added first, under a throwaway helm configuration: build resolves
     only repositories the client knows;
  4. the registry serves each pinned upstream chart at exactly the pinned digest (anonymous, the way a cluster pulls):
     for https://, the repository's index.yaml lists the version with that digest AND the archive it links hashes to it.

Fails (2) when PyYAML is missing, when no chart is found, or when --live cannot reach the registry.
"""
import glob
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

try:
    import yaml
except ImportError:
    print("FAILED MEASUREMENT: PyYAML unavailable, so no lock was read")
    sys.exit(2)

args = [a for a in sys.argv[1:] if a != "--live"]
LIVE = "--live" in sys.argv[1:]
ROOT = os.path.abspath(args[0] if args else ".")
DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
failures = []


def fail(m):
    failures.append(m)


def go_dep(d):
    """A dependency as helm's chart.Dependency marshals it: field order and omitempty as in Go."""
    out = {"name": d.get("name", "")}
    if d.get("version"):
        out["version"] = str(d["version"])
    out["repository"] = d.get("repository", "")
    for key in ("condition", "tags", "enabled", "import-values", "alias"):
        if d.get(key):
            out[key] = d[key]
    return out


def hash_req(req, lock):
    data = json.dumps([[go_dep(d) for d in req], [go_dep(d) for d in lock]], separators=(",", ":"))
    return "sha256:" + hashlib.sha256(data.encode()).hexdigest()


def http_digest(ref, version):
    """(digest, error) for chart <ref> = <repository URL>/<name> at <version>: the index entry's digest, checked
    against the SHA-256 of the archive it links."""
    repo, name = ref.rstrip("/").rsplit("/", 1)
    try:
        with urllib.request.urlopen(repo + "/index.yaml", timeout=60) as r:
            index = yaml.safe_load(r.read()) or {}
        entry = [e for e in (index.get("entries") or {}).get(name) or [] if str(e.get("version")) == str(version)]
        if not entry:
            return None, "%s/index.yaml lists no %s %s" % (repo, name, version)
        url = (entry[0].get("urls") or [""])[0]
        if not re.match(r"^https?://", url):
            url = repo + "/" + url
        with urllib.request.urlopen(url, timeout=120) as r:
            body = r.read()
    except urllib.error.HTTPError as e:
        return None, "HTTP %d" % e.code
    except Exception as e:
        return None, "unreachable: %s" % e
    archive = "sha256:" + hashlib.sha256(body).hexdigest()
    listed = "sha256:" + str(entry[0].get("digest", ""))
    if listed != archive:
        return None, "the index lists %s but the archive hashes to %s" % (listed, archive)
    return archive, None


def registry_digest(ref, version):
    if re.match(r"^https?://", ref):
        return http_digest(ref, version)
    m = re.match(r"^oci://([^/]+)/(.+)$", ref)
    if not m:
        return None, "neither an oci:// nor an https:// reference"
    host, repo = m.groups()
    try:
        with urllib.request.urlopen("https://%s/token?scope=repository:%s:pull" % (host, repo), timeout=25) as r:
            token = json.load(r).get("token", "")
        req = urllib.request.Request("https://%s/v2/%s/manifests/%s" % (host, repo, version), method="HEAD", headers={
            "Authorization": "Bearer " + token, "Accept": "application/vnd.oci.image.manifest.v1+json"})
        with urllib.request.urlopen(req, timeout=25) as r:
            return r.headers.get("Docker-Content-Digest"), None
    except urllib.error.HTTPError as e:
        return None, "HTTP %d" % e.code
    except Exception as e:  # unreachable: the caller reports it as a failed measurement
        return None, "unreachable: %s" % e


charts = sorted(glob.glob(os.path.join(ROOT, "blueprints", "*", "chart", "Chart.yaml")))
if not charts:
    print("FAILED MEASUREMENT: no chart under blueprints/*/chart/")
    sys.exit(2)
pinned = []
with_deps = []
for cy in charts:
    rel = os.path.relpath(os.path.dirname(cy), ROOT)
    meta = yaml.safe_load(open(cy)) or {}
    deps = meta.get("dependencies") or []
    ann = meta.get("annotations") or {}
    if deps:
        with_deps.append(os.path.dirname(cy))
        lp = os.path.join(os.path.dirname(cy), "Chart.lock")
        if not os.path.isfile(lp):
            fail("1: %s has dependencies but no Chart.lock: the release would resolve whatever the registry serves"
                 % rel)
        else:
            lock = yaml.safe_load(open(lp)) or {}
            ldeps = lock.get("dependencies") or []
            key = lambda d: (d.get("name"), d.get("repository"), str(d.get("version")))
            if sorted(map(key, ldeps)) != sorted(map(key, deps)):
                fail("1: %s/Chart.lock locks %s, but Chart.yaml asks for %s" % (rel, sorted(map(key, ldeps)),
                                                                              sorted(map(key, deps))))
            want = hash_req(deps, ldeps)
            if lock.get("digest") != want:
                fail("1: %s/Chart.lock digest is %s, but helm computes %s from Chart.yaml and the lock: stale or "
                     "hand-edited (run helm dependency update and commit the lock)" % (rel, lock.get("digest"), want))
    ref, version, digest = ann.get("krateo.io/upstream-chart"), ann.get("krateo.io/upstream-version"), \
        ann.get("krateo.io/upstream-digest")
    if ref or version or digest:
        if not (ref and version and digest):
            fail("2: %s names an upstream chart but not all of krateo.io/upstream-chart, -version and -digest" % rel)
            continue
        if not DIGEST.match(str(digest)):
            fail("2: %s krateo.io/upstream-digest %r is not sha256:<64 hex>" % (rel, digest))
        for d in deps:
            if "%s/%s" % (str(d.get("repository", "")).rstrip("/"), d.get("name")) == ref and str(d.get("version")) != \
                    str(version):
                fail("2: %s depends on %s %s but pins version %s" % (rel, ref, d.get("version"), version))
        pinned.append((rel, ref, str(version), str(digest)))
    elif deps:
        fail("2: %s has dependencies but pins no upstream digest (krateo.io/upstream-chart/-version/-digest)" % rel)

if LIVE:
    if shutil.which("helm") is None:
        print("FAILED MEASUREMENT: --live needs helm")
        sys.exit(2)
    for d in with_deps:
        with tempfile.TemporaryDirectory() as tmp:
            w = os.path.join(tmp, "c")
            shutil.copytree(d, w, ignore=shutil.ignore_patterns("charts"))
            env = dict(os.environ, HELM_REPOSITORY_CONFIG=os.path.join(tmp, "repositories.yaml"),
                       HELM_REPOSITORY_CACHE=os.path.join(tmp, "cache"))
            for i, repo in enumerate(sorted({str(x.get("repository", "")) for x in
                                             (yaml.safe_load(open(os.path.join(d, "Chart.yaml"))) or {}).get(
                                                 "dependencies") or [] if re.match(r"^https?://", str(x.get(
                                                     "repository", "")))})):
                a = subprocess.run(["helm", "repo", "add", "dep%d" % i, repo], capture_output=True, text=True, env=env)
                if a.returncode != 0:
                    print("FAILED MEASUREMENT: helm repo add %s: %s" % (repo, a.stderr.strip()[:200]))
                    sys.exit(2)
            r = subprocess.run(["helm", "dependency", "build", w], capture_output=True, text=True, env=env)
            if r.returncode != 0:
                fail("3: helm dependency build refuses %s: %s" % (os.path.relpath(d, ROOT), r.stderr.strip()[:300]))
    for rel, ref, version, digest in pinned:
        got, err = registry_digest(ref, version)
        if err and err.startswith("unreachable"):
            print("FAILED MEASUREMENT: %s %s: %s" % (ref, version, err))
            sys.exit(2)
        if got != digest:
            fail("4: %s pins %s:%s at %s, but the registry serves %s" % (rel, ref, version, digest, got or err))

if failures:
    for f in failures:
        print("FAIL: " + f)
    sys.exit(1)
print("OK: %d chart(s) with dependencies locked in sync with Chart.yaml; %d upstream chart(s) pinned by digest%s"
      % (len(with_deps), len(pinned), "; helm dependency build accepts every lock and the registry serves every "
                                      "pinned digest" if LIVE else " (offline: digests not compared with the registry)"))
