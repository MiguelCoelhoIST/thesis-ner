#!/bin/bash -l
# Supply currently authorized partition/node/GPU at submission.
#SBATCH --job-name=stj_19c_target_first
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=data/raw/stj_19c_target_first_%j.out
#SBATCH --error=data/raw/stj_19c_target_first_%j.err
set -euo pipefail
umask 077
: "${SLURM_JOB_ID:?Requires authorized Slurm allocation}"
: "${CUDA_VISIBLE_DEVICES:?Slurm must assign visible GPUs}"
: "${QWEN_REVISION:?Set the same immutable locally cached model commit as v1}"
cd "${SLURM_SUBMIT_DIR:?Submit from repository root}"
source venv-ner/bin/activate
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
mode="${1:?Use preflight or pilot}"
pilot_dir="${2:?Original validated 30-mention pilot directory}"
reference="${3:?Original v1 run.json}"
extra=()
case "$mode" in
    preflight) extra+=(--preflight-only) ;;
    pilot) extra+=(--preflight-run "${4:?Successful target-first preflight run.json}") ;;
    *) echo 'Use preflight or pilot'; exit 2 ;;
esac
nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv
python -u src/annotation/annotate_stj_silver_19c_target_first.py \
    --input "$pilot_dir/pilot_input.jsonl" \
    --selection-manifest "$pilot_dir/selection_manifest.json" \
    --reference-run "$reference" \
    --run-dir "data/raw/experiment_19c_target_first_${mode}_${SLURM_JOB_ID}" \
    --revision "$QWEN_REVISION" "${extra[@]}"
