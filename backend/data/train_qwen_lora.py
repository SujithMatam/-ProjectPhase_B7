"""
Fine-tuning script for Qwen 2.5 on Orthopedic Post-Op Recovery Datasets.

This script uses QLoRA (4-bit quantization with PEFT/TRL) to fine-tune
Qwen/Qwen2.5-7B-Instruct (or Qwen/Qwen2.5-3B-Instruct) on custom clinical
ShareGPT/ChatML instruction dialogues.

Prerequisites:
  pip install torch transformers datasets peft trl bitsandbytes accelerate
"""

import os
from pathlib import Path
import torch
from datasets import load_dataset
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
    TrainingArguments
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
from trl import SFTTrainer

# ============================================================================
# CONFIGURATION
# ============================================================================
MODEL_ID = "Qwen/Qwen2.5-7B-Instruct"  # or "Qwen/Qwen2.5-3B-Instruct" for lower VRAM
DATA_DIR = Path(__file__).resolve().parent / "exports"
TRAIN_FILE = str(DATA_DIR / "qwen_sft_train.jsonl")
VAL_FILE = str(DATA_DIR / "qwen_sft_val.jsonl")
OUTPUT_DIR = Path(__file__).resolve().parent / "qwen_finetuned_checkpoint"


def format_chatml(example, tokenizer):
    """Converts ShareGPT conversation list into Qwen's ChatML prompt template."""
    messages = example["conversations"]
    formatted_messages = []
    for turn in messages:
        role = "user" if turn["from"] == "user" else ("assistant" if turn["from"] == "assistant" else "system")
        formatted_messages.append({"role": role, "content": turn["value"]})
    
    text = tokenizer.apply_chat_template(formatted_messages, tokenize=False, add_generation_prompt=False)
    return {"text": text}


def train():
    print(f"[*] Loading dataset: {TRAIN_FILE}")
    dataset = load_dataset("json", data_files={"train": TRAIN_FILE, "val": VAL_FILE})

    # 4-bit Quantization Config for QLoRA
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True
    )

    print(f"[*] Loading Base Model: {MODEL_ID}")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True
    )
    model = prepare_model_for_kbit_training(model)

    # LoRA Config targeting Qwen attention & MLP projection layers
    lora_config = LoraConfig(
        r=16,
        lora_alpha=32,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM"
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Pre-process datasets with chat template
    train_dataset = dataset["train"].map(lambda x: format_chatml(x, tokenizer))
    val_dataset = dataset["val"].map(lambda x: format_chatml(x, tokenizer))

    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        per_device_train_batch_size=2,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        lr_scheduler_type="cosine",
        logging_steps=10,
        num_train_epochs=3,
        evaluation_strategy="epoch",
        save_strategy="epoch",
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        fp16=not (torch.cuda.is_available() and torch.cuda.is_bf16_supported()),
        report_to="none"
    )

    trainer = SFTTrainer(
        model=model,
        train_dataset=train_dataset,
        eval_dataset=val_dataset,
        dataset_text_field="text",
        max_seq_length=1024,
        tokenizer=tokenizer,
        args=training_args
    )

    print("[*] Starting Qwen Fine-Tuning with QLoRA...")
    trainer.train()

    print(f"[OK] Training complete! Saving LoRA adapter to: {OUTPUT_DIR}")
    model.save_pretrained(str(OUTPUT_DIR))
    tokenizer.save_pretrained(str(OUTPUT_DIR))


if __name__ == "__main__":
    train()
