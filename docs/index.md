---
type: Component
title: seaweedfs-blueprint
description: Krateo blueprint wrapping the upstream seaweedfs chart 4.54.0 as a small in-cluster S3 staging store, published on the blueprints channel.
resource: seaweedfs
tags:
  - krateo
  - blueprint
  - seaweedfs
  - s3
timestamp: 2026-11-18T00:00:00+00:00
---
# seaweedfs-blueprint

Wraps the upstream [seaweedfs](https://github.com/seaweedfs/seaweedfs) Helm chart as a Krateo blueprint, configured as a
small in-cluster S3 staging store.

| | |
|---|---|
| published | `oci://ghcr.io/krateo-blueprints/charts/seaweedfs` |
| channel | blueprints (the CompositionDefinition ships inside the archive) |
| chart version | `4.54.0`, a literal mirroring upstream |
| generated kind | `Seaweedfs`, served at `composition.krateo.io/v4-54-0` |
| namespace | `seaweedfs-system` |

It is the staging area of krateo-openstack-blueprint's backups (#309 H3c): mariadb-operator writes its physical
backups and binlog archive here, and a blueprint Job encrypts them with age and ships them offsite.

## Where to go next

- [overview.md](overview.md): the wrapper, the footprint, and why not seaweedfs-operator
- [usage.md](usage.md): the identity Secret, install, growing storage
- [configuration.md](configuration.md): what is set and why
- [api.md](api.md): the generated CRD
- [examples.md](examples.md): the example Composition
- [release.md](release.md): the tag rule and the pins
- [log.md](log.md): what changed and why
