#!/usr/bin/env python3
"""Repository-authored YAML uses block style only: no non-empty flow collection ([a, b] or {k: v}).

    hack/validate-yaml-block-style.py [repo-root]

Every YAML file this repository authors is read with PyYAML's composer, and any mapping or sequence written in flow
style with at least one entry fails. Empty collections ({} and []) are allowed: they have no block form.

Out of scope, by design:
  - blueprints/*/chart/files/upstream/: vendored upstream release manifests, kept byte for byte
    (hack/validate-vendored.py);
  - blueprints/*/chart/templates/: Go templates, not YAML until rendered.

Fails when PyYAML is missing and when no file is read.
"""
import os
import sys

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
try:
    import yaml
except ImportError:
    print("FAILED MEASUREMENT: PyYAML unavailable, so no file was read")
    sys.exit(2)

failures, read = [], 0


def walk(node, path):
    if isinstance(node, (yaml.MappingNode, yaml.SequenceNode)):
        if node.flow_style and node.value:
            failures.append("%s:%d: a non-empty flow %s" % (path, node.start_mark.line + 1,
                                                             "mapping" if isinstance(node, yaml.MappingNode) else "sequence"))
        for item in node.value:
            if isinstance(item, tuple):
                walk(item[0], path)
                walk(item[1], path)
            else:
                walk(item, path)


for dirpath, dirnames, filenames in os.walk(ROOT):
    rel = os.path.relpath(dirpath, ROOT)
    parts = rel.split(os.sep)
    if ".git" in parts or (len(parts) >= 4 and parts[0] == "blueprints" and parts[2] == "chart"
                           and parts[3] in ("templates", "files")):
        dirnames[:] = []
        continue
    for fn in filenames:
        if not fn.endswith((".yaml", ".yml")):
            continue
        p = os.path.join(dirpath, fn)
        try:
            for node in yaml.compose_all(open(p)):
                walk(node, os.path.relpath(p, ROOT))
        except yaml.YAMLError as ex:
            failures.append("%s: does not parse: %s" % (os.path.relpath(p, ROOT), str(ex).splitlines()[0]))
        read += 1

if not read:
    print("FAILED MEASUREMENT: no YAML file read")
    sys.exit(2)
if failures:
    for f in failures:
        print("FAIL: " + f)
    sys.exit(1)
print("OK: %d repository-authored YAML file(s), block style only" % read)
