{{- define "dwarpal.name" -}}{{ .Release.Name }}-dwarpal{{- end -}}

{{- define "dwarpal.labels" -}}
app.kubernetes.io/name: dwarpal
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
{{- end -}}

{{- define "dwarpal.secretName" -}}
{{- if .Values.existingSecret -}}{{ .Values.existingSecret }}{{- else -}}{{ include "dwarpal.name" . }}-keys{{- end -}}
{{- end -}}

{{- define "dwarpal.databaseUrl" -}}
{{- if .Values.postgres.enabled -}}
postgresql://{{ .Values.postgres.user }}:{{ .Values.postgres.password }}@{{ include "dwarpal.name" . }}-postgres:5432/{{ .Values.postgres.database }}
{{- else -}}{{ .Values.externalDatabaseUrl }}{{- end -}}
{{- end -}}

{{- define "dwarpal.redisUrl" -}}
{{- if .Values.redis.enabled -}}redis://{{ include "dwarpal.name" . }}-redis:6379/0{{- else -}}{{ .Values.externalRedisUrl }}{{- end -}}
{{- end -}}
