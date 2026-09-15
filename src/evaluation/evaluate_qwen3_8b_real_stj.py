import argparse
import hashlib
import json
import platform
import sys
import time
from collections import Counter
from pathlib import Path

import torch
import transformers
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
)
from transformers import AutoModelForCausalLM, AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.entity_marking import mark_entity
from src.validate_real_role_dataset import validate_file


MODEL_NAME = "Qwen/Qwen3-8B"
TRAIN_PATH = PROJECT_ROOT / "data/processed/roles_v4.jsonl"
EVAL_PATH = PROJECT_ROOT / "data/eval/roles_eval_real_candidates_v1.jsonl"
REPORT_PATH = PROJECT_ROOT / "results/experiment_17_qwen3_8b_real_stj.txt"
PREDICTIONS_PATH = (
    PROJECT_ROOT / "results/experiment_17_qwen3_8b_real_stj_predictions.json"
)
SMOKE_PATH = PROJECT_ROOT / "results/experiment_17_qwen3_8b_smoke_test.json"

LABELS = ["ARGUIDO", "TESTEMUNHA", "RELATOR", "REU", "UNKNOWN"]
INVALID_LABEL = "INVALID"
MATRIX_LABELS = LABELS + [INVALID_LABEL]
EXPECTED_EVAL_EXAMPLES = 50
EXPECTED_PER_CLASS = 10
SMOKE_EXAMPLES = 3

# These five fixed rows are part of roles_v4.jsonl. They originate from the
# synthetic hard multi-entity data and provide one demonstration per class.
DEMONSTRATION_INDICES = [831, 828, 844, 833, 834]
DEMONSTRATION_LABELS = [
    "ARGUIDO",
    "TESTEMUNHA",
    "RELATOR",
    "REU",
    "UNKNOWN",
]

SYSTEM_PROMPT = """You are a legal-role classifier for Portuguese court text.

Classify only the person inside [ENTITY] ... [/ENTITY]. Ignore roles that belong to other people.

Allowed labels and definitions:
- ARGUIDO: criminal defendant or accused person.
- TESTEMUNHA: witness.
- RELATOR: reporting judge or judge responsible for the decision.
- REU: civil defendant.
- UNKNOWN: none of the four target roles is supported by the context. This includes out-of-scope legal roles such as AUTOR, RECORRENTE, ASSISTENTE, ADVOGADO and VITIMA.

Return exactly one allowed label and no other text."""

USER_TEMPLATE = """Classify the marked target entity.

Marked text:
{marked_text}

Label:"""


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_jsonl(path):
    with path.open("r", encoding="utf-8") as dataset:
        return [json.loads(line) for line in dataset if line.strip()]


def load_eval_records(path):
    records = load_jsonl(path)
    for record in records:
        record["marked_text"] = mark_entity(
            record["text"], record["entity_start"], record["entity_end"]
        )
    return records


def require_frozen_eval_set(records):
    count, errors = validate_file(EVAL_PATH)
    if errors:
        raise ValueError("Dataset validation failed:\n" + "\n".join(errors))
    if count != EXPECTED_EVAL_EXAMPLES or len(records) != EXPECTED_EVAL_EXAMPLES:
        raise ValueError(
            f"Expected exactly {EXPECTED_EVAL_EXAMPLES} evaluation examples."
        )
    if not all(record["human_validated"] for record in records):
        raise ValueError("All evaluation examples must be human validated.")

    expected = {label: EXPECTED_PER_CLASS for label in LABELS}
    actual = dict(Counter(record["label"] for record in records))
    if actual != expected:
        raise ValueError(f"Expected 10 examples per class, found {actual}.")


def load_fixed_demonstrations(training_records):
    demonstrations = [training_records[index] for index in DEMONSTRATION_INDICES]
    actual_labels = [record["label"] for record in demonstrations]
    if actual_labels != DEMONSTRATION_LABELS:
        raise ValueError(
            "Fixed roles_v4 demonstration rows changed: "
            f"expected {DEMONSTRATION_LABELS}, found {actual_labels}."
        )
    if len(set(actual_labels)) != len(LABELS):
        raise ValueError("Few-shot demonstrations are not balanced by label.")

    unknown_demo = demonstrations[DEMONSTRATION_LABELS.index("UNKNOWN")]
    if "mandat" not in unknown_demo["text"].lower():
        raise ValueError(
            "The fixed UNKNOWN demonstration no longer represents an "
            "out-of-scope legal role."
        )
    return demonstrations


def build_messages(marked_text, setting, demonstrations):
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    if setting == "few_shot":
        for demonstration in demonstrations:
            messages.extend(
                [
                    {
                        "role": "user",
                        "content": USER_TEMPLATE.format(
                            marked_text=demonstration["text"]
                        ),
                    },
                    {"role": "assistant", "content": demonstration["label"]},
                ]
            )
    messages.append(
        {
            "role": "user",
            "content": USER_TEMPLATE.format(marked_text=marked_text),
        }
    )
    return messages


def render_prompt(tokenizer, messages):
    return tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
        enable_thinking=False,
    )


def parse_label(raw_output):
    stripped = raw_output.strip()
    return stripped if stripped in LABELS else None


def model_input_device(model):
    return model.get_input_embeddings().weight.device


def generate_outputs(model, tokenizer, prompts, batch_size):
    raw_outputs = []
    input_device = model_input_device(model)

    for start in range(0, len(prompts), batch_size):
        batch_prompts = prompts[start : start + batch_size]
        inputs = tokenizer(
            batch_prompts,
            return_tensors="pt",
            padding=True,
        ).to(input_device)

        with torch.inference_mode():
            generated = model.generate(
                **inputs,
                max_new_tokens=16,
                do_sample=False,
                temperature=0.0,
                pad_token_id=tokenizer.pad_token_id,
                eos_token_id=tokenizer.eos_token_id,
            )

        new_tokens = generated[:, inputs["input_ids"].shape[1] :]
        raw_outputs.extend(
            tokenizer.batch_decode(new_tokens, skip_special_tokens=True)
        )

    return raw_outputs


def run_setting(model, tokenizer, records, setting, demonstrations, batch_size):
    prompts = [
        render_prompt(
            tokenizer,
            build_messages(record["marked_text"], setting, demonstrations),
        )
        for record in records
    ]
    start = time.perf_counter()
    raw_outputs = generate_outputs(model, tokenizer, prompts, batch_size)
    runtime = time.perf_counter() - start
    parsed = [parse_label(output) for output in raw_outputs]
    return raw_outputs, parsed, runtime


def metric_predictions(parsed_labels):
    return [label if label is not None else INVALID_LABEL for label in parsed_labels]


def calculate_metrics(gold_labels, parsed_labels):
    predictions = metric_predictions(parsed_labels)
    precision, recall, f1, support = precision_recall_fscore_support(
        gold_labels,
        predictions,
        labels=LABELS,
        average=None,
        zero_division=0,
    )
    macro_precision, macro_recall, macro_f1, _ = (
        precision_recall_fscore_support(
            gold_labels,
            predictions,
            labels=LABELS,
            average="macro",
            zero_division=0,
        )
    )
    return {
        "count": len(gold_labels),
        "accuracy": float(accuracy_score(gold_labels, predictions)),
        "macro_precision": float(macro_precision),
        "macro_recall": float(macro_recall),
        "macro_f1": float(macro_f1),
        "invalid_output_count": sum(label is None for label in parsed_labels),
        "per_class": {
            label: {
                "precision": float(class_precision),
                "recall": float(class_recall),
                "f1": float(class_f1),
                "support": int(class_support),
            }
            for label, class_precision, class_recall, class_f1, class_support in zip(
                LABELS, precision, recall, f1, support
            )
        },
        "confusion_matrix_labels": MATRIX_LABELS,
        "confusion_matrix": confusion_matrix(
            gold_labels, predictions, labels=MATRIX_LABELS
        ).tolist(),
    }


def grouped_metrics(records, parsed_labels, field):
    results = {}
    for value in sorted({record[field] for record in records}):
        indices = [
            index for index, record in enumerate(records) if record[field] == value
        ]
        results[str(value).lower()] = calculate_metrics(
            [records[index]["label"] for index in indices],
            [parsed_labels[index] for index in indices],
        )
    return results


def distractor_metrics(records, parsed_labels):
    indices = [
        index
        for index, record in enumerate(records)
        if record["contains_distractor_role"]
    ]
    if not indices:
        return None
    return calculate_metrics(
        [records[index]["label"] for index in indices],
        [parsed_labels[index] for index in indices],
    )


def build_setting_results(records, raw_outputs, parsed_labels, runtime):
    return {
        "runtime_seconds": runtime,
        "overall": calculate_metrics(
            [record["label"] for record in records], parsed_labels
        ),
        "by_evidence_type": grouped_metrics(
            records, parsed_labels, "evidence_type"
        ),
        "by_difficulty": grouped_metrics(records, parsed_labels, "difficulty"),
        "distractor_examples": distractor_metrics(records, parsed_labels),
        "predictions": [
            {
                "id": record["id"],
                "entity": record["entity"],
                "gold": record["label"],
                "predicted": parsed,
                "valid_output": parsed is not None,
                "raw_output": raw,
                "evidence_type": record["evidence_type"],
                "difficulty": record["difficulty"],
                "contains_distractor_role": record[
                    "contains_distractor_role"
                ],
            }
            for record, raw, parsed in zip(records, raw_outputs, parsed_labels)
        ],
    }


def device_information(model, model_load_seconds):
    cuda_available = torch.cuda.is_available()
    return {
        "model": MODEL_NAME,
        "model_load_seconds": model_load_seconds,
        "platform": platform.platform(),
        "python": platform.python_version(),
        "torch": torch.__version__,
        "transformers": transformers.__version__,
        "cuda_available": cuda_available,
        "cuda_device_count": torch.cuda.device_count(),
        "cuda_devices": [
            torch.cuda.get_device_name(index)
            for index in range(torch.cuda.device_count())
        ],
        "input_device": str(model_input_device(model)),
        "model_dtype": str(next(model.parameters()).dtype),
        "device_map": {
            str(key): str(value)
            for key, value in getattr(model, "hf_device_map", {}).items()
        },
    }


def metric_summary_lines(metrics, indent=""):
    return [
        f"{indent}count: {metrics['count']}",
        f"{indent}accuracy: {metrics['accuracy']:.4f}",
        f"{indent}macro precision: {metrics['macro_precision']:.4f}",
        f"{indent}macro recall: {metrics['macro_recall']:.4f}",
        f"{indent}macro F1: {metrics['macro_f1']:.4f}",
        f"{indent}invalid outputs: {metrics['invalid_output_count']}",
    ]


def format_setting_report(title, results):
    overall = results["overall"]
    lines = [
        "=" * 88,
        title,
        "=" * 88,
        f"runtime seconds: {results['runtime_seconds']:.2f}",
        "",
        "Headline metrics:",
        *metric_summary_lines(overall),
        "",
        "Per-class metrics:",
        "label        precision  recall  F1      support",
        "-----------  ---------  ------  ------  -------",
    ]
    for label, values in overall["per_class"].items():
        lines.append(
            f"{label:<11}  {values['precision']:<9.4f}  "
            f"{values['recall']:<6.4f}  {values['f1']:<6.4f}  "
            f"{values['support']}"
        )

    labels = overall["confusion_matrix_labels"]
    width = max(10, max(len(label) for label in labels))
    lines.extend(
        [
            "",
            "Confusion matrix:",
            "Rows = gold labels; columns = predicted labels. INVALID records strict parse failures.",
            " " * (width + 2)
            + " ".join(f"{label:>{width}}" for label in labels),
        ]
    )
    for label, row in zip(labels, overall["confusion_matrix"]):
        lines.append(
            f"{label:<{width}}  "
            + " ".join(f"{value:>{width}}" for value in row)
        )

    for heading, groups in (
        ("Results by evidence_type:", results["by_evidence_type"]),
        ("Results by difficulty:", results["by_difficulty"]),
    ):
        lines.extend(["", heading])
        for group, metrics in groups.items():
            lines.append(f"  {group}:")
            lines.extend(metric_summary_lines(metrics, indent="    "))

    lines.extend(["", "Performance where contains_distractor_role=true:"])
    if results["distractor_examples"] is None:
        lines.append("No matching examples.")
    else:
        lines.extend(metric_summary_lines(results["distractor_examples"]))

    lines.extend(["", "Individual predictions:"])
    for index, prediction in enumerate(results["predictions"], start=1):
        displayed = prediction["predicted"] or INVALID_LABEL
        lines.extend(
            [
                f"{index:02d}. id={prediction['id']} | "
                f"entity={prediction['entity']} | gold={prediction['gold']} | "
                f"predicted={displayed}",
                f"    raw_output={prediction['raw_output']!r}",
            ]
        )
    return lines


def build_report(dataset_hash, device_info, demonstrations, results):
    lines = [
        "Experiment 17 - Qwen3-8B generative classification on real STJ v1",
        "",
        "EVALUATION ON THE FROZEN 50-EXAMPLE REAL STJ EVALUATION SET",
        "",
        "The dataset was used only for evaluation and was not modified or used for training.",
        "Zero-shot and few-shot settings use the same 50 examples and deterministic decoding.",
        "",
        "Configuration:",
        f"model: {MODEL_NAME}",
        "sampling: disabled",
        "temperature: 0",
        "maximum new tokens: 16",
        "chat template thinking mode: disabled",
        "strict labels: " + ", ".join(LABELS),
        f"evaluation SHA-256: {dataset_hash}",
        "",
        "Device information:",
        *[f"{key}: {value}" for key, value in device_info.items()],
        "",
        "Few-shot demonstrations:",
        "Five balanced examples selected by fixed index only from data/processed/roles_v4.jsonl.",
        "The UNKNOWN demonstration is a hard multi-entity example whose target is an out-of-scope legal representative.",
    ]
    for index, demonstration in zip(DEMONSTRATION_INDICES, demonstrations):
        lines.append(
            f"roles_v4 index {index}: label={demonstration['label']} | "
            f"text={demonstration['text']}"
        )

    lines.extend(
        [
            "",
            *format_setting_report("Setting 1 - Zero-shot", results["zero_shot"]),
            "",
            *format_setting_report("Setting 2 - Few-shot", results["few_shot"]),
        ]
    )
    return "\n".join(lines) + "\n"


def main():
    parser = argparse.ArgumentParser(description="Run Experiment 17 with Qwen3-8B.")
    parser.add_argument(
        "--smoke-only",
        action="store_true",
        help="Run the mandatory three-example smoke test and stop.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=1,
        help="Inference batch size (default: 1).",
    )
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be at least 1")

    dataset_hash = file_sha256(EVAL_PATH)
    records = load_eval_records(EVAL_PATH)
    require_frozen_eval_set(records)
    training_records = load_jsonl(TRAIN_PATH)
    demonstrations = load_fixed_demonstrations(training_records)

    print("Confirmed frozen evaluation set: 50 human-validated examples, 10 per class.")
    print("Confirmed balanced few-shot demonstrations from roles_v4 only.")
    print(f"CUDA available to PyTorch: {torch.cuda.is_available()}")

    print(f"Loading tokenizer and model: {MODEL_NAME}")
    load_start = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
    tokenizer.padding_side = "left"
    if tokenizer.pad_token_id is None:
        tokenizer.pad_token_id = tokenizer.eos_token_id
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_NAME,
        torch_dtype="auto",
        device_map="auto",
        low_cpu_mem_usage=True,
    )
    model.eval()
    model_load_seconds = time.perf_counter() - load_start
    device_info = device_information(model, model_load_seconds)
    print(json.dumps(device_info, ensure_ascii=False, indent=2))

    print("Running mandatory three-example smoke test...")
    smoke_records = records[:SMOKE_EXAMPLES]
    smoke_results = {}
    for setting in ("zero_shot", "few_shot"):
        raw, parsed, runtime = run_setting(
            model,
            tokenizer,
            smoke_records,
            setting,
            demonstrations,
            args.batch_size,
        )
        smoke_results[setting] = build_setting_results(
            smoke_records, raw, parsed, runtime
        )
        if any(label is None for label in parsed):
            SMOKE_PATH.parent.mkdir(parents=True, exist_ok=True)
            SMOKE_PATH.write_text(
                json.dumps(smoke_results, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            raise ValueError(
                f"Smoke test produced invalid {setting} output; full evaluation "
                f"was not started. Details saved to {SMOKE_PATH}."
            )

    SMOKE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SMOKE_PATH.write_text(
        json.dumps(
            {
                "experiment": 17,
                "model": MODEL_NAME,
                "status": "passed",
                "examples": SMOKE_EXAMPLES,
                "device": device_info,
                "settings": smoke_results,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Smoke test passed and saved to: {SMOKE_PATH}")

    if args.smoke_only:
        if file_sha256(EVAL_PATH) != dataset_hash:
            raise RuntimeError("Frozen evaluation dataset changed during smoke test.")
        return

    print("Running full 50-example zero-shot evaluation...")
    zero_raw, zero_parsed, zero_runtime = run_setting(
        model,
        tokenizer,
        records,
        "zero_shot",
        demonstrations,
        args.batch_size,
    )
    print("Running full 50-example few-shot evaluation...")
    few_raw, few_parsed, few_runtime = run_setting(
        model,
        tokenizer,
        records,
        "few_shot",
        demonstrations,
        args.batch_size,
    )

    results = {
        "zero_shot": build_setting_results(
            records, zero_raw, zero_parsed, zero_runtime
        ),
        "few_shot": build_setting_results(
            records, few_raw, few_parsed, few_runtime
        ),
    }
    if file_sha256(EVAL_PATH) != dataset_hash:
        raise RuntimeError("Frozen evaluation dataset changed during Experiment 17.")

    machine_results = {
        "experiment": 17,
        "title": "Qwen3-8B generative classification on frozen real STJ v1",
        "model": MODEL_NAME,
        "evaluation_dataset": "data/eval/roles_eval_real_candidates_v1.jsonl",
        "evaluation_sha256": dataset_hash,
        "evaluation_examples": len(records),
        "label_counts": dict(Counter(record["label"] for record in records)),
        "dataset_used_for_training": False,
        "device": device_info,
        "generation": {
            "do_sample": False,
            "temperature": 0.0,
            "max_new_tokens": 16,
            "enable_thinking": False,
            "batch_size": args.batch_size,
        },
        "few_shot_demonstrations": [
            {
                "roles_v4_index": index,
                "text": demonstration["text"],
                "label": demonstration["label"],
            }
            for index, demonstration in zip(
                DEMONSTRATION_INDICES, demonstrations
            )
        ],
        "settings": results,
    }

    report = build_report(dataset_hash, device_info, demonstrations, results)
    REPORT_PATH.write_text(report, encoding="utf-8")
    PREDICTIONS_PATH.write_text(
        json.dumps(machine_results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("\n" + report)
    print(f"Saved report to: {REPORT_PATH}")
    print(f"Saved machine-readable predictions to: {PREDICTIONS_PATH}")


if __name__ == "__main__":
    main()
