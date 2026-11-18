---
type: Usage
title: Installing the SeaweedFS staging store
description: The S3 identity Secret the chart requires, registering the CompositionDefinition, install, and growing storage.
resource: seaweedfs
tags:
  - krateo
  - blueprint
  - seaweedfs
  - usage
timestamp: 2026-11-18T00:00:00+00:00
---
# Usage

## The S3 identity Secret (required)

With S3 auth on (the default) the chart refuses to render unless `seaweedfs.s3.existingConfigSecret` names a Secret in
the release's namespace. Its key `seaweedfs_s3_config` holds SeaweedFS's S3 identity JSON:

```json
{
  "identities": [
    {
      "name": "mariadb-backup",
      "credentials": [
        {
          "accessKey": "<access key>",
          "secretKey": "<secret key>"
        }
      ],
      "actions": [
        "Read:mariadb-staging",
        "Write:mariadb-staging",
        "List:mariadb-staging",
        "Tagging:mariadb-staging"
      ]
    }
  ]
}
```

Provide it from your credential source, for example an External Secrets `ExternalSecret` whose target template builds
this JSON from generated keys, so the same keys reach the backup writer and the store from one place.

The upstream chart reads this Secret at render time (a `lookup`, for the checksum that rolls the gateway when the
identities change). On a cluster, the identity rendering the chart must therefore be allowed to `get` Secrets in the
release's namespace.

## Install

```sh
kubectl create namespace seaweedfs-system
helm pull oci://ghcr.io/krateo-blueprints/charts/seaweedfs --version 4.54.0 --untar --untardir /tmp/swfs
kubectl apply -n seaweedfs-system -f /tmp/swfs/seaweedfs/compositiondefinition.yaml
kubectl apply -f examples/basic/seaweedfs.yaml
```

**The namespace convention.** Cluster-prerequisite blueprints live in `<name>-system`, as krateo-openstack-blueprint
uses `openstack-system`: here `seaweedfs-system`, for the CompositionDefinition and the example Composition.

In-cluster clients reach the S3 API at `http://seaweedfs-s3.seaweedfs-system.svc:8333`.

## Growing storage

The volume server's PVC defaults to 50Gi: one full physical backup plus the binlogs not yet shipped. Upstream's
resize hook (a Job with its own image and RBAC) is off, so grow the PVC by editing it, with a StorageClass that
allows expansion, then set the same size in `seaweedfs.volume.dataDirs` so a recreated StatefulSet asks for it too.
