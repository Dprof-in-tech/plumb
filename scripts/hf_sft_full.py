"""Train a full-task Tiny Aya LoRA adapter with AlignTune on a HF GPU Job."""

from __future__ import annotations

import os

from aligntune.core.backend_factory import create_sft_trainer


def main() -> None:
    trainer = create_sft_trainer(
        model_name="CohereLabs/tiny-aya-global",
        dataset_name=os.environ.get(
            "PLUMB_SFT_DATASET", "/workspace/plumb-sft-corrections.jsonl"
        ),
        backend="trl",
        output_dir=os.environ.get("PLUMB_SFT_OUTPUT", "/workspace/sft-output"),
        num_epochs=int(os.environ.get("PLUMB_SFT_EPOCHS", "2")),
        batch_size=1,
        learning_rate=float(os.environ.get("PLUMB_SFT_LR", "2e-6")),
        max_seq_length=512,
        use_peft=True,
        lora_r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bf16=True,
        fp16=False,
        gradient_checkpointing=True,
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=2,
        max_steps=int(os.environ.get("PLUMB_SFT_MAX_STEPS", "-1")),
    )
    trainer.train()
    repo_id = os.environ.get("PLUMB_HF_REPO")
    token = os.environ.get("HF_TOKEN")
    if repo_id and token:
        from huggingface_hub import HfApi

        info = HfApi(token=token).upload_folder(
            repo_id=repo_id,
            folder_path=os.environ.get("PLUMB_SFT_OUTPUT", "/workspace/sft-output"),
            path_in_repo=os.environ.get("PLUMB_SFT_REMOTE_OUTPUT", "training/sft-output"),
            repo_type="model",
            token=token,
            commit_message="Upload full-task SFT adapter",
        )
        print(f"SFT adapter uploaded: {info.commit_url}")
    print("full-task SFT training completed")


if __name__ == "__main__":
    main()
