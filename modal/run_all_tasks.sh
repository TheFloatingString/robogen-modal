#!/bin/bash

cd "$(dirname "$0")"

for part in data/tasks/2026-01-02-part{1..5}.json; do
  echo "Processing $part..."

  while read -r line; do
    prompt=$(echo "$line" | jq -r '.prompt')
    object=$(echo "$line" | jq -r '.object')

    [ "$prompt" != "null" ] && modal run robogen_modal_conda_with_apis.py \
      --target-model-provider openrouter \
      --task-description "$prompt" \
      --target-object "$object" \
      --generate-task
  done < <(jq -c '.[]' "$part")
done
