"""Run a one-step AlignTune DPO smoke test on a CUDA Hugging Face Job."""

from __future__ import annotations

from aligntune.core.backend_factory import create_rl_trainer


def main() -> None:
    trainer = create_rl_trainer(
        model_name="CohereLabs/tiny-aya-global",
        dataset_name="/workspace/p1-preference-pairs.jsonl",
        algorithm="dpo",
        backend="trl",
        output_dir="/workspace/dpo-smoke-output",
        num_epochs=1,
        max_steps=1,
        batch_size=1,
        learning_rate=1e-6,
        max_seq_length=512,
        bf16=True,
        fp16=False,
        gradient_checkpointing=True,
        logging_steps=1,
        save_strategy="no",
    )
    trainer.train()
    print("DPO smoke training completed")


if __name__ == "__main__":
    main()
