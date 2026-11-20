{{/*
Chart name, used for the app.kubernetes.io/name label.
*/}}
{{- define "release-notes.name" -}}
{{- .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Base name for every resource. 63 characters is the DNS name limit.
If the release name already contains the chart name, it is used as is
(release "release-notes" gives "release-notes", not "release-notes-release-notes").
*/}}
{{- define "release-notes.fullname" -}}
{{- if contains .Chart.Name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}

{{/*
Chart name and version for the helm.sh/chart label.
*/}}
{{- define "release-notes.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Labels for every resource. Each template adds its own app.kubernetes.io/component
(app, database or migration) under this include.
*/}}
{{- define "release-notes.labels" -}}
helm.sh/chart: {{ include "release-notes.chart" . }}
{{ include "release-notes.selectorLabels" . }}
app.kubernetes.io/version: {{ include "release-notes.appVersion" . | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
The running app version: the image tag, or Chart.appVersion when no tag is set.
One source for the image, the version label and APP_VERSION (shown in the UI footer).
*/}}
{{- define "release-notes.appVersion" -}}
{{- .Values.image.tag | default .Chart.AppVersion }}
{{- end }}

{{/*
Image reference. With a digest, the runtime pulls by digest; the tag stays for people to read.
*/}}
{{- define "release-notes.image" -}}
{{- $ref := printf "%s:%s" .Values.image.repository (include "release-notes.appVersion" .) }}
{{- if .Values.image.digest }}
{{- $ref = printf "%s@%s" $ref .Values.image.digest }}
{{- end }}
{{- $ref }}
{{- end }}

{{/*
Name of the Postgres StatefulSet and its headless Service.
*/}}
{{- define "release-notes.postgresName" -}}
{{- printf "%s-postgres" (include "release-notes.fullname" .) | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Database host: database.host, or the Postgres Service in this chart.
Fails the render when neither is set, instead of deploying an app that cannot connect.
*/}}
{{- define "release-notes.databaseHost" -}}
{{- if .Values.database.host }}
{{- .Values.database.host }}
{{- else if .Values.postgres.enabled }}
{{- include "release-notes.postgresName" . }}
{{- else }}
{{- fail "postgres.enabled is false: set database.host to an external database" }}
{{- end }}
{{- end }}

{{/*
Env vars to reach the database, shared by the app Deployment and the migration Job.
DATABASE_PASSWORD must come first: Kubernetes replaces $(DATABASE_PASSWORD) only with
variables defined above it. The pod spec shows the placeholder, never the password.
*/}}
{{- define "release-notes.databaseEnv" -}}
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.database.existingSecret }}
      key: {{ .Values.database.passwordKey }}
- name: DATABASE_URL
  value: {{ printf "postgresql+psycopg://%s:$(DATABASE_PASSWORD)@%s:%v/%s" .Values.database.user (include "release-notes.databaseHost" .) .Values.database.port .Values.database.name | quote }}
{{- end }}

{{/*
Selector labels. Each selector also adds app.kubernetes.io/component under this include,
so the app's Service, PDB and ServiceMonitor never match the Postgres pod.
*/}}
{{- define "release-notes.selectorLabels" -}}
app.kubernetes.io/name: {{ include "release-notes.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
