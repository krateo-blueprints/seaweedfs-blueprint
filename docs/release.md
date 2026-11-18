---
type: Runbook
title: Releasing the seaweedfs blueprint
description: The tag rule for a chart that mirrors upstream's version, the pins, and how to bump upstream.
resource: seaweedfs
tags:
  - krateo
  - blueprint
  - seaweedfs
  - release
timestamp: 2026-11-18T00:00:00+00:00
---
# Release

## The tag rule

**Tag exactly the chart's version (`4.54.0`).** `Chart.yaml` carries a literal version equal to upstream's (one
upstream, so it mirrors it), not a `CHART_VERSION` placeholder, and the archive published under a tag must carry that
tag's version.

`release-tag.yaml` runs, in order:
- **preflight**: krateo-blueprints/charts `release-preflight.yaml` (1.1.0) runs `hack/release-preflight X.Y.Z`. It
  refuses a version that is not X.Y.Z, and a tag other than the version the chart, its dependency, the
  `krateo.io/upstream-version` annotation, the CompositionDefinition and the example all name.
- **package-and-push**:
  - checks the upstream pins (`hack/validate-chart-lock.py --live`);
  - builds the dependency from `Chart.lock`, after adding upstream's chart repository;
  - packages the chart with its CompositionDefinition inside;
  - pushes it to `oci://ghcr.io/krateo-blueprints/charts`.
- **publish-index**: the org publisher (`publish-chart.yaml`, 1.1.0) puts the same bytes on the **blueprints** channel.

`lint.yaml` must have succeeded on the commit. There is no pre-release channel here: the consumers' live validation
happens in krateo-openstack-blueprint (#309 H3c).

## Bumping upstream

1. Set the new version in `Chart.yaml` (`version`, the dependency, `krateo.io/upstream-version`), `appVersion` to
   upstream's, and the CompositionDefinition and example to match.
2. Run `helm dependency update blueprints/seaweedfs/chart` and commit the new `Chart.lock`.
3. Set `krateo.io/upstream-digest` to the new archive's SHA-256 (the `digest` in upstream's index.yaml for that
   version) and `seaweedfs.image.tag` to the new appVersion.
4. Run the gates. `hack/validate-render.py` fails if the new chart changed shape (a new default workload, a provider
   default, hostPath).
