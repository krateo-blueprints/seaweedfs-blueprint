---
type: Example
title: SeaweedFS as the S3 staging store
description: One Seaweedfs Composition in seaweedfs-system, with S3 auth reading its identities from a Secret the consumer provides.
resource: seaweedfs
tags:
  - krateo
  - example
  - seaweedfs
timestamp: 2026-11-18T00:00:00+00:00
---
# examples/basic

[seaweedfs.yaml](seaweedfs.yaml): kind `Seaweedfs`, served at `composition.krateo.io/v4-54-0`, in `seaweedfs-system`.

It sets only `seaweedfs.s3.existingConfigSecret`, the Secret with SeaweedFS's S3 identity JSON (key
`seaweedfs_s3_config`) that you provide, for example as an External Secrets projection of generated credentials.
[docs/usage.md](../../docs/usage.md) shows its shape. Everything else is the blueprint's default: one master, one
volume server, one filer and the S3 gateway, the `mariadb-staging` bucket, PVCs on the cluster's default StorageClass.
