#!/usr/bin/env python3
"""The chart renders a small, authenticated, provider-agnostic S3 staging store, and refuses S3 auth without identities.

    hack/validate-render.py [repo-root]

The chart is rendered with its dependency (helm dependency build from the committed Chart.lock; an https:// repository
is added under a throwaway helm configuration first) and checked:
  1. THE REFUSAL. At the defaults (S3 auth on, no existingConfigSecret) the render fails, naming
     seaweedfs.s3.existingConfigSecret. With auth off it renders without one.
  2. AUTH ON, FROM THE INPUT. With existingConfigSecret set, the S3 gateway runs with -config=/etc/sw/seaweedfs_s3_config
     from a volume of exactly that Secret, and upstream's own generated S3 credentials Secret is not rendered.
  3. THE FOOTPRINT. Exactly one master, one volume server and one filer (StatefulSets) and one S3 gateway (Deployment),
     each at 1 replica; nothing else that runs (no all-in-one, admin, worker, sftp, cosi or vector); the bucket Job
     creates the staging bucket; every container, the Job's included, requests cpu and memory and limits memory.
  4. NO PROVIDER DEFAULT. Every PersistentVolumeClaim template leaves storageClassName unset (the cluster default);
     no hostPath volume; no Service of type LoadBalancer or NodePort; no Ingress, HTTPRoute or IngressRoute; no
     cloud-provider annotation anywhere; no ClusterRole or ClusterRoleBinding (createClusterRole false).
  5. THE IMAGE. Every container runs the image values.yaml pins, at appVersion.

Fails when helm or PyYAML is missing, and when the chart renders no workload.
"""
import os
import re
import shutil
import subprocess
import sys
import tempfile

ROOT = os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else ".")
CHART = os.path.join(ROOT, "blueprints", "seaweedfs", "chart")
NS = "seaweedfs-system"
SECRET = "gate-s3-identities"
CLOUD = re.compile(r"cloud\.google\.com|\.gke\.io|gke\.io/|amazonaws\.com|service\.beta\.kubernetes\.io/aws|"
                   r"azure|digitalocean|oci\.oraclecloud|alibaba|aliyun|ibm\.com|linode|hetzner|openstack\.org/",
                   re.I)


def measurement_failed(msg):
    print("FAILED MEASUREMENT: " + msg)
    sys.exit(2)


try:
    import yaml
except ImportError:
    measurement_failed("PyYAML unavailable, so nothing was rendered")
if shutil.which("helm") is None:
    measurement_failed("helm not on PATH, so nothing was rendered")

failures = []


def fail(m):
    failures.append(m)


def staged(tmp):
    w = os.path.join(tmp, "chart")
    shutil.copytree(CHART, w)
    if not os.path.isdir(os.path.join(w, "charts")) or not os.listdir(os.path.join(w, "charts")):
        env = dict(os.environ, HELM_REPOSITORY_CONFIG=os.path.join(tmp, "repositories.yaml"),
                   HELM_REPOSITORY_CACHE=os.path.join(tmp, "cache"))
        deps = (yaml.safe_load(open(os.path.join(w, "Chart.yaml"))) or {}).get("dependencies") or []
        for i, d in enumerate(deps):
            if re.match(r"^https?://", str(d.get("repository", ""))):
                subprocess.run(["helm", "repo", "add", "dep%d" % i, d["repository"]], capture_output=True, env=env)
        r = subprocess.run(["helm", "dependency", "build", w], capture_output=True, text=True, env=env)
        if r.returncode != 0:
            measurement_failed("helm dependency build: %s" % r.stderr.strip()[:300])
    return w


def render(w, values):
    with tempfile.NamedTemporaryFile("w", suffix=".yaml", delete=False) as f:
        yaml.safe_dump(values, f)
    try:
        r = subprocess.run(["helm", "template", "seaweedfs", w, "--namespace", NS, "--kube-version", "1.36.0",
                            "-f", f.name], capture_output=True, text=True)
    finally:
        os.unlink(f.name)
    return r.returncode, r.stdout, r.stderr


def pods(docs):
    for d in docs:
        spec = d.get("spec") or {}
        if d["kind"] in ("Deployment", "StatefulSet", "DaemonSet", "Job"):
            yield d, (spec.get("template") or {}).get("spec") or {}
        elif d["kind"] == "CronJob":
            yield d, ((spec.get("jobTemplate") or {}).get("spec") or {}).get("template", {}).get("spec") or {}


def walk(o, path=""):
    if isinstance(o, dict):
        for k, v in o.items():
            yield path + "/" + str(k), k, v
            yield from walk(v, path + "/" + str(k))
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from walk(v, "%s[%d]" % (path, i))


def main():
    values = yaml.safe_load(open(os.path.join(CHART, "values.yaml")))
    chart = yaml.safe_load(open(os.path.join(CHART, "Chart.yaml")))
    img = values["seaweedfs"]["image"]
    want_image = "%s/%s:%s" % (img["registry"], img["repository"], chart["appVersion"])
    bucket = values["seaweedfs"]["s3"]["createBuckets"][0]["name"]
    with tempfile.TemporaryDirectory() as tmp:
        w = staged(tmp)
        rc, _, err = render(w, {})
        if rc == 0:
            fail("1: the defaults render with S3 auth on and no existingConfigSecret; they must be refused")
        elif "seaweedfs.s3.existingConfigSecret" not in err:
            fail("1: the defaults are refused, but not by the identity check: %s" % err.strip()[:200])
        rc, _, err = render(w, {"seaweedfs": {"s3": {"enableAuth": False}}})
        if rc != 0:
            fail("1: with S3 auth off the chart does not render without an identity Secret: %s" % err.strip()[:200])
        rc, out, err = render(w, {"seaweedfs": {"s3": {"existingConfigSecret": SECRET}}})
        if rc != 0:
            measurement_failed("the chart does not render with existingConfigSecret set: %s" % err.strip()[:300])
    docs = [d for d in yaml.safe_load_all(out) if d]
    workloads = [(d["kind"], d["metadata"]["name"]) for d, _ in pods(docs) if d["kind"] != "Job"]
    if not workloads:
        measurement_failed("the chart renders no workload")

    # 2. auth from the input
    s3 = [d for d in docs if d["kind"] == "Deployment" and d["metadata"]["name"].endswith("-s3")]
    if len(s3) != 1:
        fail("2: want one S3 gateway Deployment, got %s" % [d["metadata"]["name"] for d in s3])
    else:
        pod = s3[0]["spec"]["template"]["spec"]
        cmd = " ".join(" ".join(c.get("command") or []) + " " + " ".join(c.get("args") or []) for c in pod["containers"])
        if "-config=/etc/sw/seaweedfs_s3_config" not in cmd:
            fail("2: the S3 gateway does not run with -config=/etc/sw/seaweedfs_s3_config, so auth is off")
        secrets = [(v.get("secret") or {}).get("secretName") for v in pod.get("volumes") or [] if "secret" in v]
        if SECRET not in secrets:
            fail("2: the S3 gateway mounts secrets %s, not the existingConfigSecret %s" % (secrets, SECRET))
    generated = [d["metadata"]["name"] for d in docs if d["kind"] == "Secret" and "s3-secret" in d["metadata"]["name"]]
    if generated:
        fail("2: upstream's generated S3 credentials Secret is rendered (%s); the identities must come only from the "
             "input" % generated)

    # 3. footprint
    kinds = sorted(workloads)
    want = sorted([("StatefulSet", "seaweedfs-master"), ("StatefulSet", "seaweedfs-volume"),
                   ("StatefulSet", "seaweedfs-filer"), ("Deployment", "seaweedfs-s3")])
    if kinds != want:
        fail("3: the workloads are %s, want exactly %s" % (kinds, want))
    for d, _ in pods(docs):
        if d["kind"] != "Job" and d["spec"].get("replicas") != 1:
            fail("3: %s %s runs %s replicas, want 1" % (d["kind"], d["metadata"]["name"], d["spec"].get("replicas")))
    jobs = [(d, p) for d, p in pods(docs) if d["kind"] == "Job"]
    if not any(bucket in " ".join(" ".join(c.get("command") or []) + " " + " ".join(c.get("args") or [])
                                 for c in p.get("containers") or []) for _, p in jobs):
        fail("3: no Job creates the staging bucket %s" % bucket)
    for d, p in pods(docs):
        for c in (p.get("initContainers") or []) + (p.get("containers") or []):
            r = c.get("resources") or {}
            req = r.get("requests") or {}
            if not (req.get("cpu") and req.get("memory") and (r.get("limits") or {}).get("memory")):
                fail("3: %s %s container %s has resources %s; want cpu and memory requests and a memory limit"
                     % (d["kind"], d["metadata"]["name"], c["name"], r))

    # 4. no provider default
    for d in docs:
        for vct in (d.get("spec") or {}).get("volumeClaimTemplates") or []:
            if (vct.get("spec") or {}).get("storageClassName"):
                fail("4: %s %s claim %s names StorageClass %r; leave it unset for the cluster default" % (
                    d["kind"], d["metadata"]["name"], vct["metadata"]["name"], vct["spec"]["storageClassName"]))
        if d["kind"] == "PersistentVolumeClaim" and (d.get("spec") or {}).get("storageClassName"):
            fail("4: PVC %s names StorageClass %r" % (d["metadata"]["name"], d["spec"]["storageClassName"]))
        if d["kind"] == "Service" and (d.get("spec") or {}).get("type") in ("LoadBalancer", "NodePort"):
            fail("4: Service %s is of type %s; the staging store is in-cluster only" % (d["metadata"]["name"], d["spec"]["type"]))
        if d["kind"] in ("Ingress", "HTTPRoute", "IngressRoute", "IngressRouteTCP", "ClusterRole", "ClusterRoleBinding"):
            fail("4: %s %s is rendered" % (d["kind"], d["metadata"]["name"]))
        for path, k, v in walk(d):
            if k == "annotations" and isinstance(v, dict):
                for ak in v:
                    if CLOUD.search(str(ak)):
                        fail("4: %s %s carries the cloud-provider annotation %s" % (d["kind"], d["metadata"]["name"], ak))
    for d, p in pods(docs):
        for v in p.get("volumes") or []:
            if "hostPath" in v:
                fail("4: %s %s mounts hostPath %s; state on a node does not follow a rescheduled pod" % (
                    d["kind"], d["metadata"]["name"], v["hostPath"].get("path")))

    # 5. image
    for d, p in pods(docs):
        for c in (p.get("initContainers") or []) + (p.get("containers") or []):
            if c.get("image") != want_image:
                fail("5: %s %s container %s runs %s, want %s" % (d["kind"], d["metadata"]["name"], c["name"],
                                                                c.get("image"), want_image))

    if failures:
        for f in failures:
            print("FAIL: " + f)
        sys.exit(1)
    print("OK: refused without identities, renders with auth off; with existingConfigSecret: auth from it alone; "
          "workloads %s at 1 replica, bucket %s created, every container sized; no StorageClass, hostPath, external "
          "Service, ingress, cloud annotation or cluster RBAC; image %s"
          % (", ".join(n for _, n in kinds), bucket, want_image))


main()
