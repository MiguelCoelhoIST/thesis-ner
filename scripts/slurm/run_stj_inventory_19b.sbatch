#!/bin/bash -l
# Supply partition/node/GPU resources explicitly at sbatch submission.
#SBATCH --job-name=stj_19b_ner
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=data/raw/stj_19b_ner_%j.out
#SBATCH --error=data/raw/stj_19b_ner_%j.err

set -euo pipefail
: "${SLURM_JOB_ID:?Requires an authorized Slurm allocation}"
: "${CUDA_VISIBLE_DEVICES:?Slurm must assign visible GPUs; do not select physical GPU 3 manually}"
cd "${SLURM_SUBMIT_DIR:?Submit from the repository root}"
source venv-ner/bin/activate
export HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 HF_HUB_DISABLE_TELEMETRY=1

mode="${1:?Use smoke or full}"
extra=()
case "$mode" in
  smoke) extra+=(--max-documents 3) ;;
  full)
    smoke_manifest="${2:?Provide the successful smoke manifest path}"
    python -c 'import sys; from pathlib import Path; from src.data.prepare_stj_corpus_inventory import validate_smoke_manifest; validate_smoke_manifest(Path(sys.argv[1])); print("Smoke gate passed")' "$smoke_manifest"
    ;;
  *) echo 'Use smoke or full'; exit 2 ;;
esac
echo "Slurm job: $SLURM_JOB_ID; mode: $mode; CUDA_VISIBLE_DEVICES=$CUDA_VISIBLE_DEVICES"
nvidia-smi --query-gpu=index,name,memory.total,memory.used --format=csv
prefix="data/raw/experiment_19b_ner_${mode}_${SLURM_JOB_ID}"
python -u src/data/prepare_stj_corpus_inventory.py \
  --input-dir data/raw/iris/naoanomimizados_txt \
  --ner-model models/eduardo_extended_model \
  --taxonomy-config config/role_taxonomy_v2.json \
  --prefix "$prefix" \
  --report "results/experiment_19b_ner_${mode}_${SLURM_JOB_ID}.md" \
  --expected-unique-documents 191 --run-ner --gpu-id 0 \
  --batch-size "${NER_BATCH_SIZE:-4}" --progress-seconds 10 "${extra[@]}"
echo "Manifest: ${prefix}_manifest.json"
