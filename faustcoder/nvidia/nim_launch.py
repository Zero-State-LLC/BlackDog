"""``docker run`` argv for a local, model-free NIM (R-N003).

Launch facts are OBSERVED from the NIM for LLMs 2.1.4 docs
(https://docs.nvidia.com/nim/large-language-models/latest/, read
2026-10-31): reference/environment-variables, deployment/
air-gap-deployment, advanced-use-cases/finetune-lora,
reference/api-reference and reference/support-matrix.

- ``NIM_MODEL_PATH`` takes a local directory; with a local path no
  download occurs, and the air-gap guide says not to set NGC_API_KEY or
  HF_TOKEN. ``NIM_MODEL_NAME`` is the 1.x name, replaced by
  ``NIM_MODEL_PATH`` (reference/1.x-migration-guide).
  ``NIM_SERVED_MODEL_NAME`` is used verbatim.
- The container serves on port 8000 in every example, with
  ``/v1/health/ready`` and ``/v1/models`` next to the OpenAI routes.
- ``NIM_PEFT_SOURCE`` names a directory of ``<adapter>/adapter_config.json``
  plus ``adapter_model.safetensors``. A LoRA deployment should select a
  ``-feat_lora`` ``NIM_MODEL_PROFILE``. On vLLM the request ``model`` is
  the adapter name; on SGLang it is ``<served>:<adapter>``, which this
  client does not accept.
- The support matrix lists ``nvcr.io/nim/nvidia/vllm-model-free-nim``
  as verified on NVIDIA-GB10 (DGX Spark). The quickstart names
  ``nvcr.io/nim/nvidia/model-free-nim:2.1.4``, but on 2026-10-31 the NGC
  API listed no 2.1.x tag for that repository (latest 2.0.13).

NOT_COMPUTABLE here: startup and readiness on the cleared Spark.
"""

from __future__ import annotations

import re

from faustcoder.nvidia.container_pin import ImagePin
from faustcoder.nvidia.nim import NIMEndpoint, NIMError, is_safe_model_name
from faustcoder.spark_probe import MAX_MEMORY_CAP_BYTES

NIM_CONTAINER_PORT = 8000
CONTAINER_MODEL = "/model-repo"
CONTAINER_LORAS = "/opt/nim/loras"
SHM_SIZE = "16GB"
MODEL_FREE_REPOSITORIES = frozenset(
    {
        "nim/nvidia/vllm-model-free-nim",
        "nim/nvidia/sglang-model-free-nim",
        "nim/nvidia/model-free-nim",
    }
)
_PROFILE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,255}$")


def nim_launch_argv(
    pin: ImagePin,
    *,
    model_dir: str,
    served_model_name: str,
    port: int,
    memory_cap_bytes: int = MAX_MEMORY_CAP_BYTES,
    adapter_dir: str | None = None,
    model_profile: str | None = None,
) -> list[str]:
    """Return a ``docker run`` argv for a model-free NIM on a local model.

    ``NIM_MODEL_PATH`` points at a read-only local mount, so nothing is
    downloaded, and no NGC_API_KEY or HF_TOKEN is passed (air-gap guide).
    The port is published on 127.0.0.1 only. ``adapter_dir`` mounts LoRA
    adapters read-only at /opt/nim/loras and sets ``NIM_PEFT_SOURCE``;
    pair it with a ``-feat_lora`` ``model_profile`` from
    ``list-model-profiles``.
    """
    NIMEndpoint("127.0.0.1", port)
    if pin.repository not in MODEL_FREE_REPOSITORIES:
        raise NIMError(f"pin must be one of {sorted(MODEL_FREE_REPOSITORIES)}")
    if not 1 <= memory_cap_bytes <= MAX_MEMORY_CAP_BYTES:
        raise NIMError("memory_cap_bytes exceeds the R-001 120 GiB cap")
    if not is_safe_model_name(served_model_name):
        raise NIMError("served_model_name is not a safe model name")
    for path in (model_dir, adapter_dir):
        if path is not None and (not path.startswith("/") or ".." in path or ":" in path):
            raise NIMError("model_dir and adapter_dir must be absolute paths without '..' or ':'")
    if model_profile is not None and _PROFILE_RE.fullmatch(model_profile) is None:
        raise NIMError("model_profile is not a safe profile id")
    options: list[str] = []
    if adapter_dir is not None:
        options += ["-e", f"NIM_PEFT_SOURCE={CONTAINER_LORAS}"]
        options += ["-v", f"{adapter_dir}:{CONTAINER_LORAS}:ro"]
    if model_profile is not None:
        options += ["-e", f"NIM_MODEL_PROFILE={model_profile}"]
    return [
        "docker",
        "run",
        "--rm",
        "--gpus",
        "all",
        "--memory",
        str(memory_cap_bytes),
        "--memory-swap",
        str(memory_cap_bytes),
        "--shm-size",
        SHM_SIZE,
        "-e",
        f"NIM_MODEL_PATH={CONTAINER_MODEL}",
        "-e",
        f"NIM_SERVED_MODEL_NAME={served_model_name}",
        "-e",
        "HF_HUB_OFFLINE=1",
        "-v",
        f"{model_dir}:{CONTAINER_MODEL}:ro",
        *options,
        "-p",
        f"127.0.0.1:{port}:{NIM_CONTAINER_PORT}",
        pin.reference,
    ]
