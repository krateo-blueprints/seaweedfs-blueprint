---
type: Architecture
title: seaweedfs-blueprint architecture
description: How the wrapper chart, its pinned upstream dependency and the staging-store values fit together, and why the upstream chart and not seaweedfs-operator.
resource: seaweedfs
tags:
  - krateo
  - blueprint
  - seaweedfs
  - architecture
timestamp: 2026-11-18T00:00:00+00:00
---
# Architecture

## A wrapper around the upstream chart

`blueprints/seaweedfs/chart` depends on the upstream chart (`https://seaweedfs.github.io/seaweedfs/helm`, seaweedfs
4.54.0), pinned twice:
- `Chart.lock`, committed, so the release builds the dependency set that was reviewed (`helm dependency build` refuses
  a stale lock);
- `krateo.io/upstream-digest`, the SHA-256 of the upstream archive, which `hack/validate-chart-lock.py --live` checks
  against the repository's index and the archive itself in lint and before every release.

Its own templates add one refusal ([usage.md](usage.md)); everything else is upstream's chart with values set.

## The staging footprint

One master, one volume server, one filer and the standalone S3 gateway, each at one replica, with the staging bucket
created by upstream's post-install/post-upgrade Job. S3 authentication is on, with identities from a Secret the
consumer provides. PVCs take the cluster's default StorageClass. Nothing is exposed outside the cluster.

**High availability is not a goal.** The store holds objects only until they are shipped: the encrypted offsite copy
is the backup. Losing the staging store loses only objects not yet shipped (at most one ship interval of binlogs,
plus a base backup in flight), and the next base backup re-creates the rest. Replicating it would double the cost of a
copy that is already temporary.

## Why the upstream chart, not seaweedfs-operator

Assessed on 2026-11-18. The operator meets the bar on release cadence and misses it on maturity and CRD stability:
- **maturity:** one maintainer authors almost every change (about 1,167 contributions, against 53 for the next); 1.0.0
  shipped in October 2024 and 1.0.1 in March 2025, then about 45 patch releases, most of them in recent weeks; the
  defaulting and validating webhooks are off by default;
- **CRD stability:** around 20 CRD kinds (Seaweed, Bucket, S3Identity, S3Credentials, S3Policy and more), added under
  1.0.x patch releases, so a version number says nothing about API compatibility.

The upstream chart releases with SeaweedFS itself (roughly weekly) and has no CRDs to keep stable.

**Re-evaluation trigger.** Move to the operator when its CRD set settles (no new kinds and no breaking changes across
several consecutive releases) and it has more than one active maintainer. Its Bucket and S3Credentials CRs, fed by
External Secrets roots, would then replace the createBuckets Job and the hand-assembled identity Secret.
