---
type: Log
title: seaweedfs-blueprint changelog
description: Notable changes to the seaweedfs blueprint, with the measurements behind each decision.
resource: seaweedfs
tags:
  - krateo
  - blueprint
  - seaweedfs
  - log
timestamp: 2026-11-18T00:00:00+00:00
---
# Log

## 4.54.0 (initial)

- **The upstream seaweedfs chart 4.54.0 as an S3 staging store** for krateo-openstack-blueprint's backups (#309 H3c),
  not seaweedfs-operator: it misses the bar on maturity and CRD stability ([overview.md](overview.md), with the
  re-evaluation trigger).
- **Pinned twice:** a committed `Chart.lock`, and the archive digest (`sha256:83d6e561…`) checked live against
  upstream's index and the archive.
- **Upstream defaults overridden:**
  - hostPath storage becomes PVCs on the cluster's default StorageClass, with logs on emptyDir;
  - the cluster-wide pod ClusterRole is off, and so is the volume resize hook.
- **S3 auth on, with identities from an input Secret.** The chart refuses to render without it rather than let upstream
  generate credentials.
- **No HA, deliberately.** Staging holds only not-yet-shipped objects.
- **Namespace** `seaweedfs-system`. Every workflow `uses:` is pinned by full commit SHA. Releases run the org's
  release preflight (krateo-blueprints/charts 1.1.0).
