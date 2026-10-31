#!/usr/bin/env bash
# Conteneur OCR Surya : llama-server (boucle locale du conteneur) + service HTTP ocr-surya.
# Fail-closed : poids absents ou empreinte différente -> sortie 78, aucun service exposé.
# Si l'un des deux processus s'arrête, le conteneur s'arrête (redémarrage par l'orchestrateur).
set -euo pipefail

MODELS="${OCR_SURYA_MODELS:-/models}"
# Défaut Q8_0 : F1 identique au bf16 sur les 12 pages synthétiques du protocole S1 et ~10 %
# plus rapide (docs/ocr/SURYA.md §9). Le bf16 reste sélectionnable explicitement.
MODEL_FILE="${OCR_SURYA_MODEL_FILE:-surya-2.5-Q8_0.gguf}"
MMPROJ_FILE="${OCR_SURYA_MMPROJ_FILE:-surya-2.5-mmproj.gguf}"
THREADS="${OCR_SURYA_THREADS:-4}"
PARALLEL="${OCR_SURYA_PARALLEL:-1}"
STARTUP_TIMEOUT="${OCR_SURYA_STARTUP_TIMEOUT:-600}"
LLAMA_PORT=8091

# Empreintes officielles (Hugging Face datalab-to/surya-ocr-2.5-gguf, vérifiées LOT 2.2).
declare -A OFFICIAL=(
  [surya-2.5.gguf]=45fa3e587cf5a475f06e949fbe40e67b759dbcee1830e7effbcb172445d4b6bf
  [surya-2.5-Q8_0.gguf]=5ab34c76845f66d2882ec5c89735894b700e0a7decd08898ab962b2afb9aca57
  [surya-2.5-mmproj.gguf]=f245dbf784cf73683a273a37fefae0d0d7983b083a5d2fecf9309476f861f659
)

for name in "$MODEL_FILE" "$MMPROJ_FILE"; do
  path="$MODELS/$name"
  if [ ! -r "$path" ]; then
    echo "ocr-surya: poids absents ($name) ; voir docs/ocr/SURYA.md (licence et téléchargement)" >&2
    exit 78
  fi
  expected="${OFFICIAL[$name]:-}"
  if [ -z "$expected" ]; then
    echo "ocr-surya: fichier de poids non référencé ($name) ; refus" >&2
    exit 78
  fi
  # Contrôle d'intégrité systématique (aucun contournement prévu).
  actual="$(sha256sum "$path" | cut -d' ' -f1)"
  if [ "$actual" != "$expected" ]; then
    echo "ocr-surya: empreinte SHA-256 différente pour $name ; refus" >&2
    exit 78
  fi
done

# --cache-ram 0 : cache de prompts en mémoire hôte désactivé (défaut llama.cpp b11700 : 8 192 Mio).
# Mesuré (docs/ocr/SURYA.md §8) : sans ce réglage, le pic mémoire croît d'environ 85 Mio par page ;
# avec, il plafonne, à F1 et vitesse inchangés. Aucun prompt (dérivé d'une page) n'est conservé
# d'une requête à l'autre.
/opt/llama/llama-server -m "$MODELS/$MODEL_FILE" --mmproj "$MODELS/$MMPROJ_FILE" -ngl 0 \
  --host 127.0.0.1 --port "$LLAMA_PORT" --parallel "$PARALLEL" --ctx-size "$((PARALLEL * 12288))" \
  --alias datalab-to/surya-ocr-2.5 --jinja --special -t "$THREADS" --cache-ram 0 \
  --no-webui --log-disable &
LLAMA_PID=$!

deadline=$((SECONDS + STARTUP_TIMEOUT))
until /opt/surya/bin/python -c "import urllib.request,sys; sys.exit(0 if b'ok' in urllib.request.urlopen('http://127.0.0.1:$LLAMA_PORT/health', timeout=2).read() else 1)" 2>/dev/null; do
  if ! kill -0 "$LLAMA_PID" 2>/dev/null || [ "$SECONDS" -ge "$deadline" ]; then
    echo "ocr-surya: moteur d'inférence non prêt ; arrêt" >&2
    kill "$LLAMA_PID" 2>/dev/null || true
    exit 75
  fi
  sleep 2
done

export SURYA_INFERENCE_URL="http://127.0.0.1:$LLAMA_PORT/v1" SURYA_INFERENCE_BACKEND=llamacpp \
  SURYA_INFERENCE_AUTOSTART=false TORCH_DEVICE=cpu
# Provenance : le libellé renvoyé avec chaque lecture désigne le fichier de poids effectivement
# chargé et vérifié ci-dessus (Q8_0 ou bf16) ; il n'est pas surchargeable par l'environnement.
export OCR_SURYA_MODEL_LABEL="surya-ocr-2.5:${MODEL_FILE%.gguf}"
/opt/surya/bin/python /opt/ocr-surya/ocr_surya_service.py &
SERVICE_PID=$!

trap 'kill "$SERVICE_PID" "$LLAMA_PID" 2>/dev/null || true' TERM INT
set +e
wait -n "$LLAMA_PID" "$SERVICE_PID"
status=$?
kill "$SERVICE_PID" "$LLAMA_PID" 2>/dev/null || true
wait
exit "$status"
