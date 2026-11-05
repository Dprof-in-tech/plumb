"""Train the P1 LoRA adapter with AlignTune on a Hugging Face GPU Job."""

from __future__ import annotations

from aligntune.core.backend_factory import create_rl_trainer


def main() -> None:
    trainer = create_rl_trainer(
        model_name="CohereLabs/tiny-aya-global",
        dataset_name="/workspace/p1-preference-pairs-balanced.jsonl",
        algorithm="dpo",
        backend="trl",
        output_dir="/workspace/p1-dpo-output",
        num_epochs=3,
        max_steps=-1,
        batch_size=1,
        learning_rate=5e-7,
        max_seq_length=512,
        bf16=True,
        fp16=False,
        gradient_checkpointing=True,
        logging_steps=1,
        save_strategy="epoch",
        save_total_limit=2,
    )
    trainer.train()
    print("P1 DPO training completed")


if __name__ == "__main__":
    main()
