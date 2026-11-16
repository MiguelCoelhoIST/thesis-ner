#!/bin/bash -l
# Resources/partition/node must be confirmed and supplied at submission.
#SBATCH --job-name=stj_19c_pilot
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=data/raw/stj_19c_%j.out
#SBATCH --error=data/raw/stj_19c_%j.err
set -euo pipefail
umask 077
: "${SLURM_JOB_ID:?Requires authorized Slurm allocation}"
: "${CUDA_VISIBLE_DEVICES:?Slurm must assign visible GPUs}"
: "${QWEN_REVISION:?Set the immutable locally cached 40-hex model commit}"
cd "${SLURM_SUBMIT_DIR:?Submit from repository root}"
source venv-ner/bin/activate
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1
mode="${1:?Use preflight or pilot}"
pilot_dir="${2:?Provide the validated private pilot directory}"
extra=()
case "$mode" in
    preflight) extra+=(--preflight-only) ;;
    pilot) extra+=(--preflight-run "${3:?Provide successful preflight run.json}") ;;
    *) echo 'Use preflight or pilot'; exit 2 ;;
esac
nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv
python -u src/annotation/annotate_stj_silver_19c.py \
    --input "$pilot_dir/pilot_input.jsonl" \
    --selection-manifest "$pilot_dir/selection_manifest.json" \
    --run-dir "data/raw/experiment_19c_${mode}_${SLURM_JOB_ID}" \
    --revision "$QWEN_REVISION" "${extra[@]}"
