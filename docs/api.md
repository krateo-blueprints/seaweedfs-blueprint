---
type: API
title: seaweedfs-blueprint API
description: The CRD core-provider generates from the chart's schema.
resource: seaweedfs
tags:
  - krateo
  - blueprint
  - seaweedfs
  - api
timestamp: 2026-11-18T00:00:00+00:00
---
# API

| | |
|---|---|
| kind | `Seaweedfs` |
| group | `composition.krateo.io` |
| served version | `composition.krateo.io/v4-54-0` |
| scope | namespaced |

The served version comes from the chart version, `4.54.0`, which mirrors upstream, so an upstream bump moves it. `spec`
is the values surface in [configuration.md](configuration.md): `spec.seaweedfs` is open with a few typed keys, and a
bad value inside it is caught at render time, as `ChartRenderable=False` on the Composition.
