#!/usr/bin/env bash
# Convert the memo to DOCX and self-contained HTML (run on the allocation).
set -euo pipefail
cd "$(dirname "$0")"
pandoc MXL-006_update_memo.md -o MXL-006_update_memo.docx --resource-path=. 2>&1 | tail -2
pandoc MXL-006_update_memo.md -s --embed-resources --resource-path=. --metadata title="MXL-006 update memo (12 Sep 2026)" -o MXL-006_update_memo.html 2>/dev/null \
  || pandoc MXL-006_update_memo.md -s --self-contained --resource-path=. --metadata title="MXL-006 update memo (12 Sep 2026)" -o MXL-006_update_memo.html
ls -la MXL-006_update_memo.*
