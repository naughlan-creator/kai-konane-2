# Deployment

Kai Konane runs in three places. This directory holds two of them.

| Target | Lives in | Purpose |
|---|---|---|
| Docker Compose | `compose.yaml` (repo root) | One-command local development |
| **Kubernetes** | `deploy/k8s/` | This document. A real multi-node cluster, locally |
| Azure Container Apps | `infra/terraform/` | The deployed environment |

The same three images serve all three. Only configuration changes.

---

## Layout

```
deploy/
  k8s/
    cluster/                     Not Kubernetes objects. Never `kubectl apply`ed.
      kind-cluster.yaml            kind create cluster --config
      ingress-nginx-patch.yaml     kubectl patch --patch-file
    00-namespace.yaml
    01-secret.yaml               GITIGNORED. Local credentials only.
    05-migrate-job.yaml          Runs `flask db upgrade` once per release
    10-api-deployment.yaml       11-api-service.yaml
    20-postgres-statefulset.yaml 21-postgres-service.yaml   (headless)
    30-web-deployment.yaml       31-web-service.yaml
    40-gateway-deployment.yaml   41-gateway-service.yaml
    50-ingress.yaml
  helm/
    kai-konane/                  The same objects as a chart
```

Numbered prefixes exist because `kubectl apply -f deploy/k8s/` processes files
alphabetically: the namespace must exist before anything inside it, and the
Secret before anything that reads it. `apply` does not recurse, so
`cluster/` is skipped — which is why the two non-manifest files live there.

---

## Bootstrap

Steps 1–4 are one-time per cluster. Step 5 repeats.

```powershell
# 1. The cluster: one control-plane, two workers
kind create cluster --config deploy/k8s/cluster/kind-cluster.yaml

# 2. The ingress controller
kubectl apply -f https://kind.sigs.k8s.io/examples/ingress/deploy-ingress-nginx.yaml

# 3. Pin the controller to the control-plane (see Note 1)
kubectl patch deployment ingress-nginx-controller -n ingress-nginx `
  --patch-file deploy/k8s/cluster/ingress-nginx-patch.yaml

# 4. Load the images (see Note 2)
docker build -t kai-api:dev services/api
docker build -t kai-web:dev services/web
docker build -t kai-gateway:dev gateway
kind load docker-image kai-api:dev kai-web:dev kai-gateway:dev postgres:16-alpine `
  --name kai-konane

# 5. The application
kubectl apply -f deploy/k8s/
kubectl wait --for=condition=complete job/kai-migrate -n kai-konane --timeout=300s
kubectl exec -n kai-konane -it deploy/kai-api -- flask seed
```

Then add `127.0.0.1 kai-konane.local` to
`%WINDIR%\System32\drivers\etc\hosts` (Administrator) and open
<http://kai-konane.local:8080>.

### Verification — four checks

Pods reaching `Running` is not the same as the system working. This project has
a documented case where every page returned 200 and every image was broken.

```powershell
# 1. The whole chain: Windows -> port mapping -> ingress -> gateway -> web
curl.exe -s -o NUL -w "%{http_code}`n" -H "Host: kai-konane.local" http://localhost:8080/

# 2. /api/ routes to the api, not to web
curl.exe -s -H "Host: kai-konane.local" http://localhost:8080/api/enums

# 3. An unauthenticated call to a protected endpoint is REFUSED (expect 401)
curl.exe -s -o NUL -w "%{http_code}`n" -H "Host: kai-konane.local" http://localhost:8080/api/users

# 4. No cluster-internal hostname leaked into the HTML. NO OUTPUT is the pass.
curl.exe -s -H "Host: kai-konane.local" http://localhost:8080/ | Select-String "kai-api"
```

Check 3 matters most in principle: a deployment that silently loses
authorisation is the worst possible kind of success. Check 4 is this project's
own incident turned into an assertion.

---

## Design decisions

### Postgres is a StatefulSet, not a Deployment

A Deployment's pods are interchangeable and share one volume claim. Scale it to
two and you get two Postgres processes writing the same files. A StatefulSet
gives each pod a stable identity, its own claim from `volumeClaimTemplates`,
and ordered start/stop.

Its Service is **headless** (`clusterIP: None`). A normal Service load-balances
across endpoints, which for a single-writer database means connections landing
on whichever pod the proxy chose. Invisible with one replica; data corruption
with two.

`volumeClaimTemplates` deliberately survives `kubectl delete statefulset` —
Kubernetes does not garbage-collect those claims. Deleting the data is an
explicit `kubectl delete pvc`, which is the right amount of friction between a
person and a database.

**This is right for a laptop and for CI, and wrong for production.** A database
in a cluster makes its backups, failover, point-in-time recovery and
major-version upgrades your problem, and Kubernetes helps with none of them.
`infra/terraform/` uses a managed server for exactly that reason.

### Migrations are a Job, not an initContainer

An initContainer runs **once per pod**. With `replicas: 2`, both pods run it
simultaneously — and on a virgin database Alembic cannot arbitrate, because
`alembic_version` does not exist yet, so there is nothing to lock on. Both
start the initial migration, one wins `CREATE TABLE`, the other gets
`DuplicateTable`, both roll back, both retry. Forever.

A Job runs once. The api pods crash-loop until it completes, which is correct:
Kubernetes has no startup ordering, so components retry until their
dependencies exist.

The Job's pod template is immutable, so re-applying a changed Job is rejected.
Delete it first:

```powershell
kubectl delete job kai-migrate -n kai-konane --ignore-not-found
kubectl apply -f deploy/k8s/05-migrate-job.yaml
```

`restartPolicy: Never`, not `OnFailure`: a failed migration should leave its pod
for inspection rather than restarting in place and overwriting the logs that
explain why.

### Three probes, three questions

| Probe | Asks | On failure | Points at |
|---|---|---|---|
| `startupProbe` | Has it finished booting? | Suspends the other two | `/healthz` |
| `livenessProbe` | Is the process alive? | **Kills the container** | `/healthz` — never the database |
| `readinessProbe` | Can it serve? | Removes it from Service endpoints | `/readyz` — which does check the database |

Liveness must never touch the database. A slow query makes the probe time out,
Kubernetes kills the container, and the restart drops the connections that were
making it slow — so under load every replica dies in turn.

Postgres uses `pg_isready`, not a TCP check. Postgres accepts connections on
5432 while still replaying WAL and rejects every query with "the database
system is starting up", so a TCP probe reports ready for a server that answers
nothing.

**web has no probe that touches the api, on purpose.** If it did, an api outage
would take every web pod out of the Service and the site would return a
connection error instead of a page saying the service is unavailable. web is
built to render with the api down — its `user_loader` tolerates exactly that —
and a probe that ignores the design throws the tolerance away.

### Security contexts differ by workload, and should

api and web are plain Python processes: `runAsNonRoot`, uid 10001,
`readOnlyRootFilesystem: true`, `capabilities: drop: ["ALL"]`. Every writable
path is then declared as an `emptyDir` — `/tmp`, and `/app/instance` for the
api. That exercise is worth doing for its own sake, because it forces you to
enumerate what the application actually writes.

The gateway is different, and copying the api's context onto it is what broke
it. nginx's master starts as root and chowns its cache directories to uid 101;
with `CAP_CHOWN` dropped, root cannot chown and nginx exits `[emerg]`. It needs
four capabilities back:

```yaml
capabilities:
  drop: ["ALL"]
  add: [CHOWN, SETUID, SETGID, NET_BIND_SERVICE]
```

`drop: ["ALL"]` appears in every hardening guide as though it were free. It is
not — it is a claim about what the process does, and you have to know the
process to make it.

*Improvement not yet made:* `nginxinc/nginx-unprivileged` runs as uid 101 from
the start, listens on 8080, and needs **no** capabilities. That is a Dockerfile
change plus a port change in three manifests.

### `topologySpreadConstraints`

Without them the scheduler may put both replicas of a component on one node,
and a two-replica Deployment that looks highly available goes down entirely
when that node is drained. This is the line the three-node cluster exists to
demonstrate — on a single-node cluster it is a no-op that appears to work.

### One Ingress rule, one backend

Everything goes to the gateway. Routing `/api/` straight to the api Service
would work and is deliberately not done: the gateway is where request-id
injection, header normalisation and upstream timeouts live. Routing around it
in Kubernetes and through it everywhere else would mean the two environments
differ in exactly the layer that shapes every request.

`nginx.ingress.kubernetes.io/proxy-body-size: "10m"` is required. The api caps
uploads at 10MB via `MAX_UPLOAD_MB`; nginx-ingress defaults to 1MB. Without the
annotation an author uploading a 4MB image gets a 413 from a component they
cannot see, while the api's own limit says the file is fine.

---

## Notes — things that cost real time

### 1. The ingress controller must be pinned to the control-plane

kind's ingress manifest **tolerates** the control-plane taint but does not
**require** the control-plane node. Tolerating a taint is permission, not
preference — the scheduler is free to place the controller on a worker, and
frequently does.

Only the control-plane has the `extraPortMappings` that publish the
controller's `hostPort` to Windows. A controller on a worker makes
`localhost:8080` silently unreachable. Hence `cluster/ingress-nginx-patch.yaml`.

### 2. Images must be pre-loaded, and registry-pulled images need a workaround

kind nodes are containers with their own image store and cannot see the host's
Docker images. Registry pulls from inside this cluster are slow enough to time
out, so pre-load rather than relying on them.

`kind load docker-image` fails on any image pulled from a registry:

```
ctr: content digest sha256:...: not found
```

Docker Desktop's containerd store holds the manifest **index**, which includes
BuildKit attestation manifests (`platform.architecture: unknown`) whose blobs
were never fetched — and kind imports with `--all-platforms`. Locally built
images are unaffected because BuildKit produces a single-platform image with no
attestations.

Workaround: pull the platform-specific digest, then re-tag.

```powershell
docker manifest inspect postgres:16-alpine     # find the amd64 digest
docker pull postgres@sha256:<amd64-digest>
docker tag  postgres@sha256:<amd64-digest> postgres:16-alpine
kind load docker-image postgres:16-alpine --name kai-konane
```

The permanent fix is unchecking *Use containerd for pulling and storing images*
in Docker Desktop, at the cost of rebuilding every local image.

### 3. After a Docker Desktop restart, check the port bindings

Two different failures, and they need different fixes:

| Symptom | Cause | Fix |
|---|---|---|
| `docker port kai-konane-control-plane` is **empty** | Bindings configured but not established | `docker restart kai-konane-control-plane` |
| It shows a **different** port than the kubeconfig | kind reassigned the host port | `kind export kubeconfig --name kai-konane` |

Check `docker port` before assuming which. In the first case
`HostConfig.PortBindings` is correct while `NetworkSettings.Ports` is empty —
Docker simply failed to apply them on start.

### 4. nginx's resolver ignores `/etc/resolv.conf` search domains

The gateway's upstreams must be **fully qualified**:

```
kai-api.kai-konane.svc.cluster.local:5000
```

A short name works from `curl` and `wget` inside the same pod — those use the
search path — and fails from nginx, which queries the name verbatim. So
"I can reach it from the container" does not prove the gateway can. The symptom
is a 502 with `kai-api could not be resolved (3: Host not found)` in the nginx
error log.

Do **not** set `NGINX_LOCAL_RESOLVERS` by hand. `gateway/Dockerfile` sets
`NGINX_ENTRYPOINT_LOCAL_RESOLVERS=1`, so the nginx entrypoint reads the real
nameserver from `/etc/resolv.conf` and overwrites anything you pass.

### 5. `SESSION_COOKIE_SECURE` must be false without TLS

The local ingress serves plain HTTP. A `Secure` cookie is discarded by the
browser on an `http://` origin, so login succeeds server-side, the redirect
lands anonymous, and the user is returned to an **empty login form with no
error anywhere**. Nothing in the application can detect it — the failure is
entirely in the browser's cookie jar.

`SESSION_COOKIE_SECURE` is a separate variable from `APP_ENV` on purpose:
"in production" and "behind TLS" are different questions, and a local cluster
is where they come apart.

### 6. `API_PUBLIC_URL` must be empty

`API_BASE_URL` is where the web **process** reaches the api. `API_PUBLIC_URL`
is where the **browser** does. Setting the second to the first puts a
cluster-internal hostname into every `<img src>` on the site: every page
returns 200, every test passes, and every image is broken.

Empty means same-origin, which is correct behind the gateway. Verification
check 4 above tests this directly.

### 7. Demo passwords

`flask seed` is idempotent — *anything already present is left alone* — so it
will **never** reset a password it did not create. Losing the printed output
strands you. Set `ADMIN_PASSWORD` and `DEMO_PASSWORD` in the Secret before
first seeding.

To recover from a lost password on a throwaway database:

```powershell
kubectl exec -n kai-konane deploy/kai-api -- python -c "from app import create_app; from app.config import db; from app.models import User; app=create_app(); app.app_context().push(); [u.set_password('kaidemo123') for u in User.query.all()]; db.session.commit()"
```

### 8. `01-secret.yaml` is gitignored

A Kubernetes Secret is base64 — **encoding, not encryption**. Anyone with `get`
on Secrets in the namespace reads it in plaintext, and so does anyone with
access to etcd. The file holds local-only values and is never committed. The
Helm chart generates them instead; a real cluster uses the External Secrets
Operator or the Key Vault CSI driver so no credential passes through a manifest
at all.

### 9. Hook resources are not part of the release

The chart runs migrations as a `pre-install,pre-upgrade` hook, so Helm creates
the Job, **waits for it to complete**, and only then creates the Deployments.
That is ordering Kubernetes itself does not provide — and it is why the chart
never shows the crash-looping api pods the raw manifests do.

The cost: hook resources are not tracked in the release, so `helm uninstall`
leaves them behind. Anything a hook depends on must therefore also be a hook,
at a lower weight:

| Resource | Weight | Why |
|---|---|---|
| Secret | `-10` | Credentials for everything below |
| Postgres **Service** | `-6` | The DNS name |
| Postgres StatefulSet | `-5` | The database itself |
| Migrate Job | `0` | Needs all three |

Missing the Service from that list is a real bug and cost an install: the
database **pod** existed during pre-install while its **DNS name** did not, and
the migration failed with `could not translate host name` — which reads as a
networking problem and is an ordering problem.

Rule of thumb: if a resource is a hook, everything it depends on and everything
that depends on it must be a hook too.

This is a dev-only concern. In production `postgres.enabled: false` and
`secrets.mode: existing`, so the migration Job is the **only** hook — which is
exactly what should be one.

Helm's `--wait` does **not** wait for a hooked StatefulSet to become Ready. The
first migration attempts can hit a Service with no endpoints yet, which is why
`backoffLimit: 4` is a correctness setting rather than a nicety. With
`backoffLimit: 0` the install fails and looks like the ordering bug again.

### 10. A `---` inside a templated range is hand-managed and can be lost

`templates/services.yaml` renders three Services from one `range`. Without a
flush-left `---` before the closing `{{- end }}`, all three parse as **one**
document, duplicate keys collapse, and only the last one is created.

Nothing catches it. `helm lint` passes, `helm template` prints all three,
`helm install` reports `STATUS: deployed` — and two of four Services do not
exist. The error surfaces three layers away in the ingress controller log as
`no object matching key`, and the ingress returns 503.

`templates/hpa.yaml` and `templates/pdb.yaml` have the same shape. One object
per file would make the separator Helm's job instead; the multi-object files
are a deliberate trade for readability, and this is the price.

### 11. Any JSON on a PowerShell command line goes in a file

```powershell
# fails: PS 5.1 rewrites native arguments and eats the embedded quotes
kubectl patch deploy x --type=json -p='[{"op":"add",...}]'

# works
'[{"op":"add",...}]' | Out-File -Encoding ascii $env:TEMP\patch.json
kubectl patch deploy x --type=json --patch-file $env:TEMP\patch.json
```

kubectl reports the mangled string as an invalid request, which reads like a
problem with the patch content rather than with the shell.

### 12. metrics-server needs `--kubelet-insecure-tls` on kind

Without it every scrape fails with `x509: cannot validate certificate for
172.18.0.x because it doesn't contain any IP SANs` — kind's kubelets use
self-signed serving certificates. The HPA then shows `<unknown>/70%` and never
scales, with nothing obviously broken.

A local-cluster concession, not something to carry to a real cluster.

---

## Helm chart

`deploy/helm/kai-konane/` renders the same objects as `deploy/k8s/`, plus HPAs,
PodDisruptionBudgets and a test suite.

```powershell
helm install kai-konane deploy/helm/kai-konane `
  --namespace kai-konane --create-namespace --wait --timeout 5m

helm test kai-konane -n kai-konane --logs
```

### What the six test assertions catch

| Check | The failure it detects |
|---|---|
| api `/readyz` | Migration never ran; wrong DATABASE_URL; Postgres Service missing |
| web `/healthz` | web crash-looping |
| gateway `/` | Missing Service, no endpoints — the 503 from note 10 |
| `/api/enums` returns JSON | Gateway routing `/api/` to web instead of the api |
| `/api/users` returns **401** | Authorisation silently lost |
| No internal hostname in HTML | The broken-images incident, note 6, as a permanent assertion |

The test pod uses the **api image**, which already carries curl and is already
on every node. Pulling `curlimages/curl` would hit note 2.

`helm test` exists because every other post-install signal is a claim about the
process rather than the system. Pods Running, probes green, and
`STATUS: deployed` were all true while two of four Services did not exist.

### Autoscaling

`replicas` is omitted from a Deployment entirely when its HPA is enabled.
Leaving it set means Helm writes it on every upgrade and the HPA immediately
overwrites it — the two fight and the pod count oscillates on every deploy.

An HPA without a PDB scales to six and then lets a node drain remove five at
once. They are two halves of one question and belong together.

`scaleDown.stabilizationWindowSeconds: 300` is deliberate asymmetry: scaling up
is cheap and reversible, while scaling down during a lull that turns out to be
a gap between bursts means paying the cold start again under load. It is also
what stops an HPA on a spiky signal flapping a replica every fifteen seconds,
dropping in-flight requests each time.

### NetworkPolicy is deliberately absent

kind ships no CNI that enforces NetworkPolicy. The objects would apply cleanly,
`kubectl get networkpolicy` would list them, and nothing would be enforced —
worse than having none, because it looks like a control.

Check `kubectl get pods -n kube-system` for Calico or Cilium before adding any.

---

## What running this on Postgres uncovered

The migration chain had **never been executed against PostgreSQL**. Every
schema that ever existed — local SQLite, and Azure Postgres — was built by
`db.create_all()` from the models, because `flask seed` calls it. Alembic was
carried along and never exercised.

Three defects surfaced the first time a Kubernetes Job actually ran
`flask db upgrade`:

1. **`sa.Text(length=255)`** in the initial migration. SQLite accepts a length
   modifier on `TEXT` and ignores it; PostgreSQL rejects it outright with
   `type modifier is not allowed for type "text"`.

2. **`fe01c243a712` was autogenerated against MySQL** — note `mysql_engine`,
   `mysql_collate`, and `activity_ibfk_1` constraint names. Its purpose there
   was a case rename: MySQL's initial migration produced lowercase table names
   and this recreated them in camelCase. On PostgreSQL the initial migration
   already produces camelCase, so every statement is either a duplicate
   `CREATE TABLE` or a reference to a table that never existed. Now a
   documented no-op, with the revision kept so the chain stays linked.

3. **The initContainer race** described above.

Four revisions existed and none of them worked. Three databases were involved
and the migrations only ever matched the one nobody deployed.

The general lesson: a migration chain that has never been exercised is not a
migration chain, it is a directory of Python files. Putting migrations in a Job
is what made them run for the first time.

---

## Observability

`deploy/k8s/monitoring/` runs Prometheus and Grafana in the cluster. Plain
manifests, not a chart: they are cluster infrastructure rather than part of the
application release, and mixing the two would make `helm uninstall kai-konane`
a decision about whether monitoring survives.

```powershell
# The images are registry pulls, so they need the digest workaround from note 2
kubectl apply -f deploy/k8s/monitoring/

kubectl port-forward -n monitoring svc/grafana 3000:3000     # admin / kaidemo123
kubectl port-forward -n monitoring svc/prometheus 9090:9090
```

### Logs and metrics answer different questions

`logging_setup.py` answers *what happened to this ONE request* — arrive with a
request id, leave with a story. Metrics answer *what is happening to ALL of
them* — arrive with a suspicion, leave with a rate.

Counting log lines to get a rate is a query whose cost grows with traffic, so
it gets slower exactly as the incident gets worse. A metric is pre-aggregated:
the cost of asking is constant.

That difference produces opposite decisions about the same endpoints. `/healthz`
is **filtered out of logs** (per-GB ingestion, and probe noise buries real
traffic) and **kept in metrics** (no volume cost, and a probe's request rate is
a real signal — if it stops, the kubelet is wrong, not the app). Static assets
are filtered from both.

### The three things that are easy to get wrong

**Label cardinality.** A time series exists per distinct label combination.
Labelling by `request.path` makes `/api/users/1` and `/api/users/2` separate
series, so the metric's cardinality becomes the number of rows in the users
table. `request.url_rule.rule` gives `/api/users/<int:user_id>` — one series
per endpoint.

The fallback matters as much as the rule: without `<unmatched>` for a `None`
`url_rule`, a scanner probing random URLs creates a series per request, and an
unauthenticated attacker can exhaust the monitoring server's memory just by
making requests. Denial of service delivered through the observability stack.

web's `templatise()` is a heuristic doing the same job for outbound calls — it
collapses numeric and UUID segments. A slug would still leak one series per
story. The correct fix is call sites passing the template; this buys most of
the benefit for none of the churn.

**Multiprocess collection.** api runs 2 gunicorn workers, web runs 4. Each is a
separate process with a separate registry, so without `PROMETHEUS_MULTIPROC_DIR`
a scrape reports whichever worker answered — half the real numbers for api, a
quarter for web. Consistently wrong, which is worse than obviously broken.

`gunicorn.conf.py` provides the two lifecycle hooks only the master can:
clearing the directory at start (files surviving a restart inflate every
counter forever) and `mark_process_dead` on worker exit (a dead worker's files
are summed in forever otherwise).

**Histogram buckets are permanent.** The library default runs to 10s, useless
for a service whose interesting range is 10ms to 1s — everything lands in one
bucket and the p95 is a flat line. Changing buckets later loses history. The
0.75 boundary exists because the level-prediction endpoint loads a joblib model
and sits just under a second.

### Two subtleties in the instrumentation

The in-flight gauge is decremented in `teardown_request`, **not**
`after_request`. `after_request` does not run when a view raises, so the gauge
would climb by one on every unhandled exception and never come down — a gauge
that only rises is how a perfectly healthy service comes to look permanently
overloaded.

web measures its **own** api calls (`api_client_*`). web makes no database
queries, so every slow page is slow because of an upstream call: timing the
page says it was slow, timing the calls says which one. `api_client_failures_
total` is separate from the status-code counter because those failures have no
HTTP status at all — a timeout or refused connection has no response to read a
status from, and they are the ones that mean the api is *gone* rather than
erroring.

### Prometheus discovers targets, it is not told about them

A pod is scraped if it carries `prometheus.io/scrape: "true"`. That inverts
ownership: the service declares it wants monitoring, rather than the monitoring
config knowing about every service. Scale web from 2 to 6 and six targets
appear within a scrape interval, with nothing edited.

The `labelmap` relabel rule turns `app.kubernetes.io/component: api` into a
`component="api"` label on every series, so dashboards can say
`sum by (component) (...)`. Without it you would match on pod name — which
changes on every rollout, so the graphs would break on every deploy.

The cost is RBAC: Prometheus needs read access to nodes, services, endpoints
and pods cluster-wide. It is the one pod here that legitimately mounts a
service account token.

### Alerts describe symptoms

Four rules, all describing something a **user** would notice. None alert on CPU,
memory or replica count: a cause that is not currently hurting anyone is not an
alert, it is a dashboard panel.

| Rule | Fires on | `for` |
|---|---|---|
| `KaiHighErrorRate` | 5xx as a **ratio** of all requests > 5% | 5m |
| `KaiApiUnreachableFromWeb` | Failures with no HTTP status at all | 3m |
| `KaiSlowResponses` | p95 latency > 1s | 10m |
| `KaiTargetDown` | `up == 0` — pod alive, not answering | 2m |

Ratios, not counts: ten errors in a million requests is healthy, ten in twenty
is an outage. A count-based rule pages for the first and misses the second.

Every rule has a `for` clause. Without one a single bad scrape pages someone.

**Deliberately absent**, and the reasoning is the point:

- `KaiNoTraffic` — would fire every night on a demo cluster nobody is using. An
  alert that fires when nothing is wrong trains people to ignore alerts, which
  costs more than the coverage it adds.
- `KaiHighCpu` / `KaiHighMemory` — causes. High CPU hurting nobody is not an
  incident; high CPU that *is* hurting someone already shows up as
  `KaiSlowResponses`.
- `KaiPodRestarted` — Kubernetes restarting a pod is the system **working**.

Validate before applying — `promtool` ships inside the Prometheus image:

```powershell
kubectl exec -n monitoring deploy/prometheus -- promtool check rules /etc/prometheus/alerts.yml
```

### Alertmanager is not here

Prometheus decides **whether** an alert fires. Alertmanager decides **who hears
about it, grouped how, and how often** — deduplication, silences, routing to
email or Slack. People conflate the two.

It is omitted because the skill on display is rule design, and firing rules are
visible in Prometheus's own `/alerts` page. Adding it is routing plumbing.

### Dashboards are code

The datasource and the dashboard are provisioned from ConfigMaps, and
`allowUiUpdates: false` means UI edits are not persisted. That is deliberate:
the alternative is a dashboard whose definitive version is whatever someone
last dragged around at 2am, recoverable only from a backup.

Grafana's own database is an `emptyDir` — thrown away on restart, and
everything still works. That is the test of whether provisioning is real: **if
deleting Grafana's database loses something, it was not provisioned.**

### Notes specific to this stack

**13. `PROMETHEUS_MULTIPROC_DIR` must be created by the application, not the
Dockerfile or gunicorn.** `prometheus_client` memory-maps a file the moment a
metric is *created*, which happens at import time. gunicorn's `on_starting`
hook creates the directory — but only gunicorn runs it, so `flask db upgrade`,
`flask seed` and `flask check` all died with
`FileNotFoundError: /tmp/prometheus/gauge_livesum_1.db`.

Adding observability broke the **migrations**, on the one code path with
nothing to do with serving traffic. `metrics.py` now creates the directory
itself, before the metric definitions.

A `RUN mkdir` in the Dockerfile does not fix it: `/tmp` is an `emptyDir` mount
in Kubernetes, which masks whatever the image had there. **A directory created
at build time under a mount point does not exist at run time.**

**14. `rule_files` is a top-level key**, a sibling of `global` and
`scrape_configs` — not nested inside `global`. `global` holds scalars;
`rule_files` is a list of paths. They are related in behaviour
(`global.evaluation_interval` governs how often the rules run) while being
siblings in structure, which is what makes the mistake easy.

**15. `pip freeze > requirements.txt` is not how you add a dependency.** It
captured 352 packages from a dev venv — including `reportlab`, `git-filter-repo`
and `mysqlclient`, a driver for a database this project stopped using years ago.
The build failed on `pkg-config: not found`, three layers from the cause. It was
also written as UTF-16 by PowerShell's `>`, so git saw a binary file.

`pip freeze` reproduces an *environment*; a curated `requirements.txt` declares
a *dependency set*. The 29-line file is a design artefact.

---

## Teardown

```powershell
kubectl delete -f deploy/k8s/            # the application
kubectl delete -f deploy/k8s/monitoring/ # Prometheus and Grafana
kubectl delete pvc -n kai-konane --all   # the database volume, explicitly
kind delete cluster --name kai-konane    # everything
```

`kubectl delete -f deploy/k8s/` does not recurse, so `monitoring/` needs its own
line — the same property that keeps `cluster/` out of an apply.

The PVC step is separate on purpose — see the StatefulSet note above.
