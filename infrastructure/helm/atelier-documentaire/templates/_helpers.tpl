{{- define "atelier.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- define "atelier.fullname" -}}
{{- if .Values.fullnameOverride }}{{ .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}{{ else }}{{ include "atelier.name" . }}{{ end -}}
{{- end -}}
{{- define "atelier.labels" -}}
app.kubernetes.io/name: {{ include "atelier.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
{{- define "atelier.serviceAccountName" -}}
{{- if .Values.serviceAccount.create }}{{ default (include "atelier.fullname" .) .Values.serviceAccount.name }}{{ else }}default{{ end -}}
{{- end -}}
{{- define "atelier.scratchClaim" -}}
{{- default (printf "%s-scratch" (include "atelier.fullname" .)) .Values.scratch.existingClaim -}}
{{- end -}}
