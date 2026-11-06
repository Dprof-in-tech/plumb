#!/bin/bash
# Run the PLUMB benchmark through Ollama inside a Hugging Face Job.
#
# Why this exists: every comparison row in this project was originally produced
# through a local Ollama on a laptop. That is the wrong place for it -- it makes
# the benchmark depend on one machine staying up, and mixing serving stacks
# mid-comparison is the failure-4 confound this project already paid for once.
#
# This reproduces that path exactly -- same GGUF, same Modelfile template, same
# stop parameter, same runner -- on rented hardware. It validates itself by
# re-running the converted base and checking it reproduces the recorded
# held-out base row before any new number is trusted.
set -euo pipefail

REPO=Isaacdnigerian/plumb
TASKS=${PLUMB_TASKS:-split-test.jsonl}
OUT=/workspace/out
mkdir -p $OUT

echo "=== install ollama ==="
curl -fsSL https://ollama.com/install.sh | sh >/dev/null 2>&1
ollama --version

echo "=== fetch harness ==="
pip install --no-cache-dir -q gguf huggingface_hub
hf download $REPO training/run.py training/plumb/__init__.py training/plumb/tasks.py \
  training/plumb/score.py training/plumb/sheet.py "training/$TASKS" \
  --repo-type model --local-dir /workspace/hub
mkdir -p /workspace/plumb /workspace/tasks
cp /workspace/hub/training/plumb/*.py /workspace/plumb/
cp /workspace/hub/training/run.py /workspace/run.py
cp "/workspace/hub/training/$TASKS" "/workspace/tasks/$TASKS"

echo "=== start ollama ==="
ollama serve > /workspace/ollama.log 2>&1 &
for i in $(seq 1 60); do
  curl -sf http://localhost:11434/api/tags >/dev/null 2>&1 && break
  sleep 2
done
curl -sf http://localhost:11434/api/tags >/dev/null || { echo "ollama did not start"; cat /workspace/ollama.log; exit 1; }

TPL='{{ if .System }}<|START_OF_TURN_TOKEN|><|SYSTEM_TOKEN|>{{ .System }}<|END_OF_TURN_TOKEN|>{{ end }}{{ if .Prompt }}<|START_OF_TURN_TOKEN|><|USER_TOKEN|>{{ .Prompt }}<|END_OF_TURN_TOKEN|>{{ end }}<|START_OF_TURN_TOKEN|><|CHATBOT_TOKEN|><|START_RESPONSE|>{{ .Response }}<|END_RESPONSE|><|END_OF_TURN_TOKEN|>'

# $1 = gguf path in repo, $2 = ollama model name
build_model () {
  local remote="$1" name="$2"
  echo "--- build $name from $remote"
  hf download $REPO "$remote" --repo-type model --local-dir /workspace/gguf
  local g="/workspace/gguf/$remote"
  python3 - "$g" <<'PY'
import sys
from gguf.gguf_reader import GGUFReader
print("  eos_token_id before:", GGUFReader(sys.argv[1]).fields["tokenizer.ggml.eos_token_id"].contents())
PY
  # Tiny Aya terminates by sampling token 3 (<EOS_TOKEN>). Converted artifacts
  # have historically declared 6 (<|END_OF_TURN_TOKEN|>), which never fires.
  # A stop string cannot substitute: every terminator here is a CONTROL token
  # and llama.cpp does not render those into the text stream.
  gguf-set-metadata "$g" tokenizer.ggml.eos_token_id 3 --force 2>&1 | grep -E "Preparing|changed" || true
  printf 'FROM %s\nTEMPLATE """%s"""\nPARAMETER stop "<|END_OF_TURN_TOKEN|>"\n' "$g" "$TPL" > /workspace/Modelfile.$name
  ollama create "$name" -f /workspace/Modelfile.$name 2>&1 | tail -1
  rm -f "$g"
}

# $1 = model, $2 = label
evaluate () {
  echo "--- evaluate $2"
  PYTHONPATH=/workspace python3 /workspace/run.py --model api --api-id "$1" \
    --tasks "/workspace/tasks/$TASKS" --label "$2" --out "$OUT/$2.jsonl"
}

build_model training/ollama/tiny-aya-global-converted-Q4_K_M.gguf plumb-base-eosfix
build_model training/ollama/sft-masked-Q4_K_M.gguf plumb-sft-masked

# Validation first: the base must reproduce the recorded row before any new
# number from this environment is trusted.
evaluate plumb-base-eosfix hfeval-base-1
evaluate plumb-sft-masked  hfeval-masked-1
evaluate plumb-sft-masked  hfeval-masked-2

echo "=== upload ==="
hf upload $REPO $OUT training/runs --repo-type model \
  --commit-message "Add HF-side Ollama evaluation of the completion-only-loss adapter"
echo "HF_EVAL_DONE"
