#!/bin/bash
# Empacota em .tgz só os arquivos criados ou reescritos depois do marcador, para os jobs de coleta
# do workflow passarem o resultado ao job que publica. Sem arquivo novo, não cria o pacote.
# Uso: scripts/empacotar.sh saida.tgz marcador caminho...
set -euo pipefail
saida=$1; marcador=$2; shift 2
existentes=()
for c in "$@"; do
  if [ -e "$c" ]; then existentes+=("$c"); fi
done
if [ ${#existentes[@]} -eq 0 ]; then echo "Nada a empacotar."; exit 0; fi
lista=$(mktemp)
find "${existentes[@]}" -type f -newer "$marcador" -print0 > "$lista"
if [ ! -s "$lista" ]; then echo "Nada a empacotar."; exit 0; fi
tar czf "$saida" --null -T "$lista"
echo "Pacote $saida: $(tr -cd '\0' < "$lista" | wc -c) arquivos, $(du -h "$saida" | cut -f1)"
