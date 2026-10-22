#!/bin/bash
# Prepara o ambiente das sessões na nuvem: dependências Python para rodar pytest.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "$CLAUDE_PROJECT_DIR"
pip install --quiet --disable-pip-version-check -r requirements-dev.txt
