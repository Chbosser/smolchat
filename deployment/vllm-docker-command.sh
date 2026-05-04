#!/usr/bin/env bash

sudo docker run --rm \
  -v ~/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  --ipc=host \
  -e VLLM_API_KEY="$VLLM_API_KEY" \
  vllm/vllm-openai-cpu:latest-x86_64 \
  HuggingFaceTB/SmolLM2-135M-Instruct \
  --host 0.0.0.0 \
  --port 8000 \
  --api-key "$VLLM_API_KEY" \
  --dtype float32 \
  --max-model-len 128 \
  --max-num-batched-tokens 128 \
  --gpu-memory-utilization 0.50
