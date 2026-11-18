# seaweedfs-blueprint

## What is this

A Krateo blueprint wrapping the upstream [seaweedfs](https://github.com/seaweedfs/seaweedfs) Helm chart **4.54.0** as a
small in-cluster **S3 staging store**: one master, one volume server, one filer and the S3 gateway, S3 auth on.
Published to `oci://ghcr.io/krateo-blueprints/charts/seaweedfs` on the **blueprints** channel. It is the staging area
of krateo-openstack-blueprint's backups (#309 H3c): mariadb-operator writes physical backups and its binlog archive
here, and a blueprint Job encrypts them with age and ships them offsite.

## Install

Provide the S3 identity Secret (key `seaweedfs_s3_config`) in `seaweedfs-system`, register the CompositionDefinition,
and apply [examples/basic](examples/basic). Without `seaweedfs.s3.existingConfigSecret` the Composition refuses to
render, with the reason on its status. See [docs/usage.md](docs/usage.md).

## Configure

`spec.seaweedfs` is passed to the upstream chart; the blueprint sets a staging footprint, PVCs on the cluster's
default StorageClass, auth from the input Secret, the `mariadb-staging` bucket and resource requests. See
[docs/configuration.md](docs/configuration.md).

## Why the upstream chart, not seaweedfs-operator

Assessed 2026-11-18. The operator releases often, but:
- **Maturity:** one maintainer authors almost every change; about 45 patch releases came after 1.0.1, most in recent
  weeks; its webhooks are off by default.
- **CRD stability:** around 20 CRD kinds were added under 1.0.x patches.

The upstream chart releases with SeaweedFS and has no CRDs.

**Re-evaluation trigger:** the operator's CRD set settles (no new kinds and no breaking changes across several
releases) and it has more maintainers. Then its Bucket and S3Credentials CRs, fed by External Secrets roots, replace
the createBuckets Job and the hand-assembled identity Secret. [docs/overview.md](docs/overview.md).

## High availability: not a goal

The store holds objects only until they are shipped; the encrypted offsite copy is the backup. Losing staging loses
only objects not yet shipped (at most one ship interval of binlogs, plus a base backup in flight), and the next base
backup re-creates the rest.

## Versioning

One upstream, so the chart's version is a literal equal to upstream's (`4.54.0`), and the release tag must be exactly
it. The dependency is pinned by a committed `Chart.lock` and by the upstream archive's digest
(`krateo.io/upstream-digest`), checked live. [docs/release.md](docs/release.md).

## Namespace

`seaweedfs-system`, the convention for cluster-prerequisite blueprints (`<name>-system`, as krateo-openstack-blueprint
uses `openstack-system`).

## Examples

[examples/basic](examples/basic): one Composition naming its identity Secret. See [docs/examples.md](docs/examples.md).

## Docs

- [docs/overview.md](docs/overview.md): the wrapper, the footprint, the operator assessment
- [docs/usage.md](docs/usage.md): the identity Secret, install, growing storage
- [docs/configuration.md](docs/configuration.md): what is set and why
- [docs/api.md](docs/api.md): the generated CRD
- [docs/release.md](docs/release.md): the tag rule and the pins
- [docs/log.md](docs/log.md): what changed and why

## Develop & release

`lint.yaml` runs the gates in `hack/`:
- `validate-chart-lock.py --live`: the lock and the upstream digest;
- `validate-version-mirror.py`;
- `validate-render.py`: the refusal, auth from the input, the footprint and no provider default;
- `validate-release-wiring.py`: the preflight chain and every `uses:` pinned;
- `validate-yaml-block-style.py`;
- `helm lint`.

`preflight-refs.yaml` resolves the image. Tag exactly the chart's version; the release runs `hack/release-preflight`
first. [docs/release.md](docs/release.md).
