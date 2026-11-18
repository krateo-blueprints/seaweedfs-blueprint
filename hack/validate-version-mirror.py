#!/usr/bin/env python3
"""The chart mirrors its one upstream: every place that names a version names the same one.

    hack/validate-version-mirror.py [repo-root]

One upstream chart, so this chart's version is a LITERAL equal to upstream's (krateo-blueprints/charts PUBLISHING.md,
charts that version independently), and the release tag must be exactly it (hack/release-preflight). Checked:
  1. Chart.yaml version == its dependency on upstream seaweedfs == krateo.io/upstream-version; the dependency's
     repository/name is krateo.io/upstream-chart; sources list this repository first and upstream's.
  2. appVersion is upstream's appVersion for that chart version, and the image tag values.yaml pins is appVersion.
     The upstream appVersion is read from the dependency archive under charts/ when it is there (helm dependency
     build), and from the lock gate's live check otherwise.
  3. compositiondefinition.yaml installs oci://ghcr.io/krateo-blueprints/charts/<chart> at that version, in namespace
     seaweedfs-system (the <name>-system convention for cluster-prerequisite blueprints).
  4. examples/basic: one Composition of kind Seaweedfs at composition.krateo.io/v<X-Y-Z> of that version.

Fails when PyYAML is missing and when no chart is found.
"""
import glob
import os
import re
import sys
import tarfile

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
REPO = "https://github.com/krateo-blueprints/seaweedfs-blueprint"
NAMESPACE = "seaweedfs-system"


def measurement_failed(msg):
    print("FAILED MEASUREMENT: " + msg)
    sys.exit(2)


try:
    import yaml
except ImportError:
    measurement_failed("PyYAML unavailable, so nothing was read")

charts = sorted(glob.glob(os.path.join(ROOT, "blueprints", "*", "chart", "Chart.yaml")))
if not charts:
    measurement_failed("no chart under blueprints/*/chart/")
failures = []
checked = []

for cy_path in charts:
    chart_dir = os.path.dirname(cy_path)
    bp = os.path.dirname(chart_dir)
    name = os.path.basename(bp)
    cy = yaml.safe_load(open(cy_path)) or {}
    ver = str(cy.get("version"))
    ann = cy.get("annotations") or {}
    if not re.fullmatch(r"\d+\.\d+\.\d+", ver):
        failures.append("%s: Chart.yaml version %r is not a literal X.Y.Z" % (name, ver))
    if cy.get("name") != name:
        failures.append("%s: Chart.yaml name is %r, its directory is blueprints/%s" % (name, cy.get("name"), name))
    deps = cy.get("dependencies") or []
    up = [d for d in deps if "%s/%s" % (str(d.get("repository", "")).rstrip("/"), d.get("name")) ==
          ann.get("krateo.io/upstream-chart")]
    if len(up) != 1:
        failures.append("%s: no single dependency is krateo.io/upstream-chart %r" % (name, ann.get("krateo.io/upstream-chart")))
    else:
        if str(up[0].get("version")) != ver:
            failures.append("%s: depends on upstream %s, but the chart version is %s" % (name, up[0].get("version"), ver))
    if str(ann.get("krateo.io/upstream-version")) != ver:
        failures.append("%s: krateo.io/upstream-version %r, chart version %s" % (name, ann.get("krateo.io/upstream-version"), ver))
    if (cy.get("sources") or [])[:2] != [REPO, "https://github.com/seaweedfs/seaweedfs"]:
        failures.append("%s: sources %s, want [%s, https://github.com/seaweedfs/seaweedfs]" % (name, cy.get("sources"), REPO))
    app = str(cy.get("appVersion"))
    values = yaml.safe_load(open(os.path.join(chart_dir, "values.yaml"))) or {}
    img = ((values.get(name) or {}).get("image") or {})
    if str(img.get("tag")) != app:
        failures.append("%s: values pin image tag %r, appVersion is %s" % (name, img.get("tag"), app))
    archives = glob.glob(os.path.join(chart_dir, "charts", "%s-%s.tgz" % (up[0]["name"] if up else name, ver)))
    if archives:
        with tarfile.open(archives[0]) as t:
            member = [m for m in t.getmembers() if m.name.endswith("/Chart.yaml") and m.name.count("/") == 1][0]
            upstream_app = str((yaml.safe_load(t.extractfile(member)) or {}).get("appVersion"))
        if upstream_app != app:
            failures.append("%s: appVersion %s, but upstream %s's appVersion is %s" % (name, app, ver, upstream_app))
    cd = yaml.safe_load(open(os.path.join(bp, "compositiondefinition.yaml"))) or {}
    spec = ((cd.get("spec") or {}).get("chart") or {})
    if spec.get("url") != "oci://ghcr.io/krateo-blueprints/charts/" + name or str(spec.get("version")) != ver:
        failures.append("%s: its CompositionDefinition installs %s %s, want oci://ghcr.io/krateo-blueprints/charts/%s %s"
                        % (name, spec.get("url"), spec.get("version"), name, ver))
    if (cd.get("metadata") or {}).get("namespace") != NAMESPACE:
        failures.append("%s: its CompositionDefinition is in namespace %r, the convention is %s"
                        % (name, (cd.get("metadata") or {}).get("namespace"), NAMESPACE))
    kind = "".join(p[:1].upper() + p[1:] for p in re.split(r"[-_]", name))
    served = "composition.krateo.io/v" + ver.replace(".", "-")
    found = []
    for p in sorted(glob.glob(os.path.join(ROOT, "examples", "basic", "*.yaml"))):
        for doc in yaml.safe_load_all(open(p)):
            if doc and str(doc.get("apiVersion", "")).startswith("composition.krateo.io/"):
                found.append((doc.get("kind"), doc.get("apiVersion"), (doc.get("metadata") or {}).get("namespace")))
    if found != [(kind, served, NAMESPACE)]:
        failures.append("examples/basic holds %s, want exactly [(%s, %s, %s)]" % (found, kind, served, NAMESPACE))
    checked.append("%s %s (appVersion %s%s)" % (name, ver, app, ", upstream archive read" if archives else ""))

if failures:
    for f in failures:
        print("FAIL: " + f)
    sys.exit(1)
print("OK: %s mirrors its upstream everywhere" % "; ".join(checked))
