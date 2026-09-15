#!/bin/bash -l

#SBATCH --job-name=qwen3_full
#SBATCH --partition=hlt_msc
#SBATCH --nodelist=g06
#SBATCH --gres=gpu:RTX_6000_24GB:1
#SBATCH --cpus-per-task=4
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH --output=results/qwen3_full_%j.out
#SBATCH --error=results/qwen3_full_%j.err

cd /cfs/home/u036585/thesis-ner
source venv/bin/activate

echo "===== HOST ====="
hostname

echo "===== DATE ====="
date

echo "===== GPU ====="
nvidia-smi

echo "===== PYTHON ====="
which python

echo "===== EXPERIMENT 17 FULL EVALUATION ====="
python src/evaluation/evaluate_qwen3_8b_real_stj.py
