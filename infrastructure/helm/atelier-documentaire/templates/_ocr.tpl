{{/*
OCR : Surya par défaut, exécuté en conteneur annexe (sidecar) du pod qui analyse les
documents. Le service n'écoute que sur 127.0.0.1 : aucune exposition réseau, aucun Service
Kubernetes, d'où des sondes « exec » (les sondes httpGet visent l'IP du pod).
Tesseract reste sélectionnable explicitement (ocr.backend: tesseract), sans repli automatique.
*/}}
{{- define "atelier.ocrEnv" -}}
- { name: TRANSLATOR_OCR_BACKEND, value: {{ .Values.ocr.backend | quote }} }
{{- if eq .Values.ocr.backend "surya" }}
- { name: TRANSLATOR_SURYA_OCR_URL, value: "http://127.0.0.1:8093" }
- { name: TRANSLATOR_SURYA_OCR_ALLOWED_HOSTS, value: "127.0.0.1" }
- { name: TRANSLATOR_SURYA_OCR_TIMEOUT_SECONDS, value: {{ .Values.ocr.surya.timeoutSeconds | quote }} }
- { name: TRANSLATOR_SURYA_WEIGHTS_LICENSE_ACKNOWLEDGED, value: {{ .Values.ocr.surya.weightsLicenseAcknowledged | quote }} }
{{- end }}
{{- end -}}

{{- define "atelier.ocrSuryaProbe" -}}
exec:
  command: ["/opt/surya/bin/python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8093/health', timeout=3)"]
{{- end -}}

{{- define "atelier.ocrSuryaSidecar" -}}
{{- if eq .Values.ocr.backend "surya" }}
- name: ocr-surya
  image: "{{ .Values.ocr.surya.image }}:{{ .Values.ocr.surya.tag }}"
  imagePullPolicy: {{ .Values.image.pullPolicy }}
  env:
    - { name: OCR_SURYA_BIND, value: "127.0.0.1" }
    - { name: OCR_SURYA_ALLOW_NON_LOOPBACK, value: "0" }
    - { name: OCR_SURYA_MODEL_FILE, value: {{ .Values.ocr.surya.modelFile | quote }} }
    - { name: OCR_SURYA_THREADS, value: {{ .Values.ocr.surya.threads | quote }} }
  startupProbe:
    {{- include "atelier.ocrSuryaProbe" . | nindent 4 }}
    periodSeconds: 10
    timeoutSeconds: 5
    failureThreshold: 60
  readinessProbe:
    {{- include "atelier.ocrSuryaProbe" . | nindent 4 }}
    periodSeconds: 15
    timeoutSeconds: 5
  livenessProbe:
    {{- include "atelier.ocrSuryaProbe" . | nindent 4 }}
    periodSeconds: 30
    timeoutSeconds: 5
    failureThreshold: 3
  resources:
    {{- toYaml .Values.ocr.surya.resources | nindent 4 }}
  securityContext: { allowPrivilegeEscalation: false, readOnlyRootFilesystem: true, capabilities: { drop: [ALL] } }
  volumeMounts:
    - { name: ocr-tmp, mountPath: /tmp }
    - { name: surya-models, mountPath: /models, readOnly: true }
{{- end }}
{{- end -}}

{{- define "atelier.ocrSuryaVolumes" -}}
{{- if eq .Values.ocr.backend "surya" }}
- name: ocr-tmp
  emptyDir: { sizeLimit: 1Gi }
- name: surya-models
  persistentVolumeClaim: { claimName: {{ .Values.ocr.surya.modelClaim }}, readOnly: true }
{{- end }}
{{- end -}}
