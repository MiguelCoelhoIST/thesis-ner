#!/bin/bash -l
# SUSPENDED historical Experiment 19b prototype, NOT an Experiment 19c job.
# Requires 40 legacy candidates/suggested_label, separate REFERENCE taxonomy;
# no other_roles support. Preserved only; a new execution needs authorization.
# Resource template copied from Experiment 17; verify current INESC availability.
#SBATCH --job-name=qwen3_19b
#SBATCH --partition=hlt_msc
#SBATCH --gres=gpu:RTX_6000_24GB:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=data/raw/experiment_19b_%j.out
#SBATCH --error=data/raw/experiment_19b_%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Run only inside an authorized Slurm allocation}"
cd "${SLURM_SUBMIT_DIR:?Submit from the repository root}"
source venv-ner/bin/activate
# Keep Slurm's CUDA_VISIBLE_DEVICES mapping; never hard-code physical GPU 3.
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1

mode="${1:-smoke}"
extra=()
case "$mode" in
    smoke) extra+=(--smoke-only) ;;
    full) ;;
    *) echo "Use smoke or full"; exit 2 ;;
esac
# QWEN_REVISION should be the immutable commit of the authorized local snapshot.
python -u src/annotation/annotate_role_candidates_qwen.py \
    --input data/raw/experiment_19a_annotation_batch01_v1.jsonl \
    --output "data/raw/experiment_19b_${mode}_${SLURM_JOB_ID}_silver.jsonl" \
    --run-metadata "data/raw/experiment_19b_${mode}_${SLURM_JOB_ID}_run.json" \
    --report "results/experiment_19b_${mode}_${SLURM_JOB_ID}_aggregate.md" \
    --revision "${QWEN_REVISION:-main}" --device cuda --seed 42 "${extra[@]}"
