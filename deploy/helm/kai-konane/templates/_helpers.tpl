{{/*
Name helpers.

Kubernetes caps most object names at 63 characters and rejects a trailing
hyphen. `trunc 63 | trimSuffix "-"` is not superstition: a long release name
produces an object that fails to create, and the error names the object rather
than the release.
*/}}

{{- define "kai.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "kai.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Labels, split in two on purpose.

`kai.labels` goes on the object. Only `kai.selectorLabels` goes in a selector,
because a Deployment's selector is IMMUTABLE -- put the version label in it and
the next `helm upgrade` fails permanently with "field is immutable" and the
release is stuck with no way forward but uninstall.
*/}}
{{- define "kai.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{ include "kai.selectorLabels" . }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "kai.selectorLabels" -}}
app.kubernetes.io/name: {{ include "kai.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{/*
Per-component variants. `component` is what separates api pods from web pods
inside one release. Called as:
  {{- include "kai.componentLabels" (dict "root" . "component" "api") | nindent 4 }}
*/}}
{{- define "kai.componentLabels" -}}
{{ include "kai.labels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{- define "kai.componentSelector" -}}
{{ include "kai.selectorLabels" .root }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/*
The image reference. Refuses to render without a tag.

`required` turns a missing tag into a refused install with a readable message
rather than a Deployment that pulls whatever `latest` points at today. Same
decision as the image_tag validation in your Terraform -- third time you have
made it, and worth noticing that it keeps being the right one.
*/}}
{{- define "kai.image" -}}
{{- $tag := .root.Values.image.tag | default .root.Chart.AppVersion -}}
{{- $tag = required "image.tag must be set. Refusing to deploy an unpinned image." $tag -}}
{{- if .root.Values.image.registry -}}
{{- printf "%s/%s:%s" .root.Values.image.registry .component $tag -}}
{{- else -}}
{{- printf "kai-%s:%s" .component $tag -}}
{{- end -}}
{{- end -}}

{{/*
Which Secret holds the runtime credentials.
*/}}
{{- define "kai.secretName" -}}
{{- if eq .Values.secrets.mode "existing" -}}
{{- required "secrets.existingSecret is required when secrets.mode is 'existing'" .Values.secrets.existingSecret -}}
{{- else -}}
{{- printf "%s-secrets" (include "kai.fullname" .) -}}
{{- end -}}
{{- end -}}

{{/*
Database host: the in-cluster StatefulSet, or the external server.
*/}}
{{- define "kai.databaseHost" -}}
{{- if .Values.postgres.enabled -}}
{{- printf "%s-postgres" (include "kai.fullname" .) -}}
{{- else -}}
{{- required "externalDatabase.host is required when postgres.enabled is false" .Values.externalDatabase.host -}}
{{- end -}}
{{- end -}}

{{/*
Fully-qualified service name, for the gateway's nginx upstreams.

nginx's resolver ignores the search domains in /etc/resolv.conf, so a short
name resolves from curl inside the pod and fails from nginx. You debugged this
in B4 -- the helper exists so it cannot be got wrong again.
*/}}
{{- define "kai.fqdn" -}}
{{- printf "%s-%s.%s.svc.cluster.local" (include "kai.fullname" .root) .component .root.Release.Namespace -}}
{{- end -}}