import hashlib
import json
import sys
import time
from pathlib import Path

from transformers import AutoModelForCausalLM, AutoTokenizer


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.evaluate_qwen3_8b_real_stj import (
    MODEL_NAME,
    TRAIN_PATH,
    build_setting_results,
    device_information,
    load_eval_records,
    load_fixed_demonstrations,
    load_jsonl,
    run_setting,
)
from src.validate_real_role_dataset import validate_file


CHALLENGE_PATH = (
    PROJECT_ROOT / "data/eval/roles_eval_multi_entity_challenge_v1.jsonl"
)
REPORT_PATH = (
    PROJECT_ROOT / "results/qwen3_8b_multi_entity_diagnostic_v1.txt"
)
PREDICTIONS_PATH = (
    PROJECT_ROOT / "results/qwen3_8b_multi_entity_diagnostic_v1.json"
)
EXPECTED_EXAMPLES = 5
BATCH_SIZE = 1


def file_sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require_valid_challenge_set(records):
    count, errors = validate_file(CHALLENGE_PATH)
    if errors:
        raise ValueError("Challenge dataset validation failed:\n" + "\n".join(errors))
    if count != EXPECTED_EXAMPLES or len(records) != EXPECTED_EXAMPLES:
        raise ValueError(
            f"Expected exactly {EXPECTED_EXAMPLES} challenge records, "
            f"found {len(records)}."
        )
    if not all(record["human_validated"] for record in records):
        raise ValueError("All challenge records must be human validated.")


def load_model_and_tokenizer():
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
    return model, tokenizer


def format_setting(title, results):
    overall = results["overall"]
    lines = [
        title,
        "-" * len(title),
        f"accuracy: {overall['accuracy']:.4f}",
        f"invalid outputs: {overall['invalid_output_count']}",
        f"runtime seconds: {results['runtime_seconds']:.2f}",
        "",
        "Individual predictions:",
    ]
    for index, prediction in enumerate(results["predictions"], start=1):
        predicted = prediction["predicted"] or "INVALID"
        lines.extend(
            [
                f"{index}. id: {prediction['id']}",
                f"   target entity: {prediction['entity']}",
                f"   gold label: {prediction['gold']}",
                f"   predicted label: {predicted}",
                f"   raw output: {prediction['raw_output']!r}",
                f"   valid output: {str(prediction['valid_output']).lower()}",
            ]
        )
    return lines


def main():
    challenge_hash = file_sha256(CHALLENGE_PATH)
    records = load_eval_records(CHALLENGE_PATH)
    require_valid_challenge_set(records)

    training_records = load_jsonl(TRAIN_PATH)
    demonstrations = load_fixed_demonstrations(training_records)

    print("Confirmed five-record multi-entity challenge set.")
    print("Loading the unchanged Experiment 17 Qwen3-8B configuration...")
    load_start = time.perf_counter()
    model, tokenizer = load_model_and_tokenizer()
    model_load_seconds = time.perf_counter() - load_start
    device_info = device_information(model, model_load_seconds)

    setting_results = {}
    for setting in ("zero_shot", "few_shot"):
        print(f"Evaluating {setting}...")
        raw_outputs, parsed_labels, runtime = run_setting(
            model,
            tokenizer,
            records,
            setting,
            demonstrations,
            BATCH_SIZE,
        )
        setting_results[setting] = build_setting_results(
            records,
            raw_outputs,
            parsed_labels,
            runtime,
        )

    if file_sha256(CHALLENGE_PATH) != challenge_hash:
        raise RuntimeError("Challenge dataset changed during the diagnostic.")

    report_lines = [
        "Qwen3-8B multi-entity diagnostic v1",
        "",
        "QUALITATIVE FIVE-EXAMPLE DIAGNOSTIC - NOT A STATISTICAL EVALUATION",
        "",
        "These examples are separate from the frozen 50-example Experiment 17 evaluation set and are not included in its headline metrics.",
        "",
        "Configuration:",
        f"model: {MODEL_NAME}",
        "prompt and definitions: imported unchanged from evaluate_qwen3_8b_real_stj.py",
        "entity marking: canonical offset-derived [ENTITY] entity [/ENTITY]",
        "decoding: do_sample=False, temperature=0, max_new_tokens=16",
        "output parsing: exact allowed-label match; invalid outputs are not remapped",
        f"challenge SHA-256: {challenge_hash}",
        "",
        "Device information:",
        *[f"{key}: {value}" for key, value in device_info.items()],
        "",
        *format_setting("Zero-shot", setting_results["zero_shot"]),
        "",
        *format_setting("Few-shot", setting_results["few_shot"]),
    ]
    report = "\n".join(report_lines) + "\n"

    machine_results = {
        "title": "Qwen3-8B multi-entity diagnostic v1",
        "type": "qualitative diagnostic, not a statistical evaluation",
        "included_in_experiment_17_headline_metrics": False,
        "model": MODEL_NAME,
        "dataset": "data/eval/roles_eval_multi_entity_challenge_v1.jsonl",
        "dataset_sha256": challenge_hash,
        "examples": len(records),
        "device": device_info,
        "generation": {
            "do_sample": False,
            "temperature": 0.0,
            "max_new_tokens": 16,
            "batch_size": BATCH_SIZE,
            "enable_thinking": False,
        },
        "settings": setting_results,
    }

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(report, encoding="utf-8")
    PREDICTIONS_PATH.write_text(
        json.dumps(machine_results, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print("\n" + report)
    print(f"Saved report to: {REPORT_PATH}")
    print(f"Saved machine-readable results to: {PREDICTIONS_PATH}")


if __name__ == "__main__":
    main()
