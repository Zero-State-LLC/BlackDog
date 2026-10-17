"""Torch implementations of the Spark throughput probes.

Imported only when a probe has already passed the CUDA, local-path
and memory-cap gates. Importing this module does not import torch.
"""

from __future__ import annotations

import time
from typing import Any

from faustcoder.spark_probe import ProbeRequest, estimate_decoder_weight_bytes, load_model_config


class TorchBackend:
    """Load one local model and run both probes against it."""

    def __init__(self) -> None:
        self._model: Any = None
        self._failure: dict[str, Any] | None = None

    def inference(self, request: ProbeRequest) -> dict[str, Any]:
        model = self._ensure_model(request)
        if isinstance(model, dict):
            return model
        return _prefill_and_decode(model, request)

    def lora_step(self, request: ProbeRequest) -> dict[str, Any]:
        model = self._ensure_model(request)
        if isinstance(model, dict):
            return model
        return _lora_step_on_module(model, request)

    def _ensure_model(self, request: ProbeRequest) -> Any:
        if self._failure is not None:
            return self._failure
        if self._model is not None:
            return self._model
        if request.model_path is None:
            self._failure = _result("skipped", "no_local_model")
            return self._failure
        try:
            self._model = _load(request)
        except _ProbeSkip as exc:
            self._failure = _result("skipped", exc.reason)
            return self._failure
        except _ProbeFail as exc:
            self._failure = _result("error", exc.reason)
            return self._failure
        return self._model


def inference(request: ProbeRequest) -> dict[str, Any]:
    """Run inference on a freshly loaded model.

    The CLI does not use this. It keeps one ``TorchBackend`` so the LoRA
    step reuses the weights.
    """
    return TorchBackend().inference(request)


def lora_step(request: ProbeRequest) -> dict[str, Any]:
    """Run a LoRA step on a freshly loaded model. See ``inference``."""
    return TorchBackend().lora_step(request)


class _ProbeSkip(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class _ProbeFail(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _result(
    status: str,
    reason: str | None,
    *,
    tokens_per_second: float | None = None,
    peak_memory_bytes: int | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": status,
        "reason": reason,
        "tokens_per_second": tokens_per_second,
        "peak_memory_bytes": peak_memory_bytes,
        "detail": detail or {},
    }


def _load(request: ProbeRequest) -> Any:
    import torch
    from transformers import AutoModelForCausalLM

    if request.model_path is None:
        raise _ProbeSkip("no_local_model")
    if not torch.cuda.is_available():
        raise _ProbeSkip("no_cuda")
    if not torch.cuda.is_bf16_supported():
        raise _ProbeSkip("bf16_unavailable")
    config = load_model_config(request.model_path)
    if config is None or estimate_decoder_weight_bytes(config) is None:
        raise _ProbeSkip("config_incomplete")
    _limit_cuda_fraction(torch, request.memory_cap_bytes)
    dtype = torch.bfloat16
    path = str(request.model_path)
    try:
        try:
            model = AutoModelForCausalLM.from_pretrained(
                path,
                dtype=dtype,
                local_files_only=True,
                low_cpu_mem_usage=True,
            )
        except TypeError:
            model = AutoModelForCausalLM.from_pretrained(
                path,
                torch_dtype=dtype,
                local_files_only=True,
                low_cpu_mem_usage=True,
            )
        model.to("cuda")
    except torch.cuda.OutOfMemoryError as exc:
        raise _ProbeFail("oom") from exc
    except (OSError, RuntimeError) as exc:
        raise _ProbeFail("load_failed") from exc
    return model


def _limit_cuda_fraction(torch: Any, memory_cap_bytes: int) -> None:
    reported = int(torch.cuda.get_device_properties(0).total_memory)
    if reported < memory_cap_bytes:
        return
    fraction = min(0.95, memory_cap_bytes / reported)
    try:
        torch.cuda.set_per_process_memory_fraction(fraction)
    except RuntimeError:
        return


def _prefill_and_decode(model: Any, request: ProbeRequest) -> dict[str, Any]:
    import torch

    config = load_model_config(request.model_path) if request.model_path else None
    vocab = config.get("vocab_size") if isinstance(config, dict) else None
    if isinstance(vocab, bool) or not isinstance(vocab, int) or vocab <= 1:
        return _result("error", "config_incomplete")
    if hasattr(model, "eval"):
        model.eval()
    device = torch.device("cuda")
    ids = torch.randint(0, vocab, (1, request.seq_len), device=device)
    torch.cuda.reset_peak_memory_stats()
    produced = 0
    start = time.perf_counter()
    try:
        with torch.inference_mode():
            logits = _logits(model(input_ids=ids))
            next_id = logits[:, -1:].argmax(dim=-1)
            produced = 1
            while produced < request.max_new_tokens:
                if time.monotonic() >= request.deadline:
                    break
                logits = _logits(model(input_ids=next_id))
                next_id = logits[:, -1:].argmax(dim=-1)
                produced += 1
    except torch.cuda.OutOfMemoryError:
        return _result("error", "oom")
    except (RuntimeError, TypeError, AttributeError):
        return _result("error", "forward_failed")
    elapsed = max(time.perf_counter() - start, 1e-9)
    processed = request.seq_len + max(produced - 1, 0)
    peak = int(torch.cuda.max_memory_allocated())
    torch.cuda.empty_cache()
    return _result(
        "completed",
        None,
        tokens_per_second=processed / elapsed,
        peak_memory_bytes=peak,
        detail={
            "method": "prefill_plus_greedy_decode",
            "dtype": "bfloat16",
            "seq_len": request.seq_len,
            "new_tokens": produced,
        },
    )


def _lora_step_on_module(model: Any, request: ProbeRequest) -> dict[str, Any]:
    import torch

    config = load_model_config(request.model_path) if request.model_path else None
    vocab = config.get("vocab_size") if isinstance(config, dict) else None
    if isinstance(vocab, bool) or not isinstance(vocab, int) or vocab <= 1:
        return _result("error", "config_incomplete")
    if hasattr(model, "train"):
        model.train()
    wrapped = _replace_first_linear(model, request.lora_rank)
    if wrapped is None:
        return _result("error", "no_linear")
    trainable = [param for param in model.parameters() if param.requires_grad]
    if not trainable:
        return _result("error", "no_linear")
    optimizer = torch.optim.AdamW(trainable, lr=1e-4)
    device = torch.device("cuda")
    torch.cuda.reset_peak_memory_stats()
    start = time.perf_counter()
    completed_steps = 0
    try:
        for _step in range(request.lora_steps):
            if time.monotonic() >= request.deadline:
                break
            ids = torch.randint(0, vocab, (1, request.seq_len), device=device)
            optimizer.zero_grad(set_to_none=True)
            loss = _loss(model(input_ids=ids, labels=ids))
            loss.backward()
            optimizer.step()
            completed_steps += 1
    except torch.cuda.OutOfMemoryError:
        return _result("error", "oom")
    except (RuntimeError, TypeError, AttributeError):
        return _result("error", "forward_failed")
    if completed_steps == 0:
        torch.cuda.empty_cache()
        return _result("skipped", "deadline")
    elapsed = max(time.perf_counter() - start, 1e-9)
    processed = completed_steps * request.seq_len
    peak = int(torch.cuda.max_memory_allocated())
    torch.cuda.empty_cache()
    return _result(
        "completed",
        None,
        tokens_per_second=processed / elapsed,
        peak_memory_bytes=peak,
        detail={
            "method": "adamw_lora_on_first_linear",
            "dtype": "bfloat16",
            "seq_len": request.seq_len,
            "steps": completed_steps,
            "rank": request.lora_rank,
            "alpha": 1,
        },
    )


def _logits(output: Any) -> Any:
    logits = output.logits if hasattr(output, "logits") else output
    if not hasattr(logits, "argmax"):
        raise TypeError("model output has no logits")
    return logits


def _loss(output: Any) -> Any:
    if hasattr(output, "loss") and output.loss is not None:
        return output.loss
    if hasattr(output, "pow"):
        return output.float().pow(2).mean()
    raise TypeError("model output has no loss")


def _replace_first_linear(root: Any, rank: int) -> Any:
    from torch import nn

    for parent in root.modules():
        for name, child in list(parent.named_children()):
            if isinstance(child, nn.Linear):
                wrapped = _lora_linear(child, rank)
                setattr(parent, name, wrapped)
                return wrapped
    return None


def _lora_linear(base: Any, rank: int) -> Any:
    import torch
    from torch import nn

    class LoRALinear(nn.Module):
        def __init__(self, frozen: Any, lora_rank: int) -> None:
            super().__init__()
            self.base = frozen
            self.base.requires_grad_(False)
            self.A = nn.Parameter(torch.empty(lora_rank, frozen.in_features))
            self.B = nn.Parameter(torch.zeros(frozen.out_features, lora_rank))
            nn.init.normal_(self.A, std=0.02)

        def forward(self, inputs: Any) -> Any:
            return self.base(inputs) + (inputs @ self.A.t() @ self.B.t())

    return LoRALinear(base, rank)
