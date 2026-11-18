---
type: Configuration
title: seaweedfs-blueprint configuration
description: What the wrapper sets in the upstream chart's values, and why.
resource: seaweedfs
tags:
  - krateo
  - blueprint
  - seaweedfs
  - configuration
timestamp: 2026-11-18T00:00:00+00:00
---
# Configuration

The root takes `global` and `seaweedfs`. `seaweedfs` is passed to the upstream chart, whose values.yaml documents every
key. Helm validates this schema against values that carry the subchart's full defaults, so the object is open: the keys
below are typed, and any other passes through.

| value | default | why |
|---|---|---|
| `global.seaweedfs.createClusterRole` | `false` | upstream's ClusterRole may create, patch and delete every pod in the cluster |
| `seaweedfs.image` | `docker.io/chrislusf/seaweedfs:4.54` | named in full, so preflight-refs resolves it; the tag is appVersion |
| `seaweedfs.master.replicas`, `.volume.replicas`, `.filer.replicas`, `.s3.replicas` | `1` | a staging store ([overview.md](overview.md)) |
| `seaweedfs.master.data`, `.filer.data`, `.volume.dataDirs` | PVC, 1Gi / 5Gi / 50Gi, `storageClass: ""` | upstream defaults to hostPath, which does not follow a rescheduled pod; empty means the cluster default |
| `*.logs` | `emptyDir` | upstream defaults to hostPath |
| `seaweedfs.volume.resizeHook.enabled` | `false` | an extra Job, image and RBAC ([usage.md](usage.md)) |
| `seaweedfs.filer.s3.enabled` | `false` | the standalone gateway serves S3 |
| `seaweedfs.s3.enabled`, `.enableAuth` | `true`, `true` | authenticated S3 |
| `seaweedfs.s3.existingConfigSecret` | `""` (required) | the S3 identities are an input |
| `seaweedfs.s3.createBuckets` | `mariadb-staging` | the staging bucket |
| `*.resources` | requests and memory limits | sized for staging |
| `seaweedfs.s3.ingress.enabled`, `.service.type` | `false`, `ClusterIP` | in-cluster only |

Nothing provider-specific is defaulted: no StorageClass, no load-balancer type, no cloud annotation
(`hack/validate-render.py` refuses each).
