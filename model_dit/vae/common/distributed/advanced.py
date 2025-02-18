"""
Advanced distributed functions for sequence parallel.
"""

from typing import Optional, Tuple
import torch.distributed as dist

from .basic import get_global_rank, get_world_size

_DATA_PARALLEL_GROUP = None
_SEQUENCE_PARALLEL_GROUP = None
_SEQUENCE_PARALLEL_CPU_GROUP = None


def get_data_parallel_group() -> Optional[dist.ProcessGroup]:
    """
    Get data parallel process group.
    """
    return _DATA_PARALLEL_GROUP


def get_sequence_parallel_group() -> Optional[dist.ProcessGroup]:
    """
    Get sequence parallel process group.
    """
    return _SEQUENCE_PARALLEL_GROUP


def get_sequence_parallel_cpu_group() -> Optional[dist.ProcessGroup]:
    """
    Get sequence parallel CPU process group.
    """
    return _SEQUENCE_PARALLEL_CPU_GROUP


def get_data_parallel_rank() -> int:
    """
    Get data parallel rank.
    """
    group = get_data_parallel_group()
    return dist.get_rank(group) if group else get_global_rank()


def get_data_parallel_world_size() -> int:
    """
    Get data parallel world size.
    """
    group = get_data_parallel_group()
    return dist.get_world_size(group) if group else get_world_size()


def get_sequence_parallel_rank() -> int:
    """
    Get sequence parallel rank.
    """
    group = get_sequence_parallel_group()
    return dist.get_rank(group) if group else 0


def get_sequence_parallel_world_size() -> int:
    """
    Get sequence parallel world size.
    """
    group = get_sequence_parallel_group()
    return dist.get_world_size(group) if group else 1


def get_model_shard_cpu_group() -> Optional[dist.ProcessGroup]:
    """
    Get the CPU process group of model sharding.
    """
    return _MODEL_SHARD_CPU_GROUP


def init_sequence_parallel(sequence_parallel_size: int):
    """
    Initialize sequence parallel.
    """
    global _DATA_PARALLEL_GROUP
    global _SEQUENCE_PARALLEL_GROUP
    global _SEQUENCE_PARALLEL_CPU_GROUP
    assert dist.is_initialized()
    world_size = dist.get_world_size()
    rank = dist.get_rank()
    data_parallel_size = world_size // sequence_parallel_size
    for i in range(data_parallel_size):
        start_rank = i * sequence_parallel_size
        end_rank = (i + 1) * sequence_parallel_size
        ranks = range(start_rank, end_rank)
        group = dist.new_group(ranks)
        cpu_group = dist.new_group(ranks, backend="gloo")
        if rank in ranks:
            _SEQUENCE_PARALLEL_GROUP = group
            _SEQUENCE_PARALLEL_CPU_GROUP = cpu_group


def init_model_shard_cpu_group(sharding_strategy: str, device_mesh: Optional[Tuple] = None):
    """
    Initialize CPU process group of model sharding.
    """
    global _MODEL_SHARD_CPU_GROUP
    assert dist.is_initialized()
    world_size = dist.get_world_size()
    rank = dist.get_rank()
    if device_mesh is not None:
        num_shards_per_group = device_mesh[1]
    elif "HYBRID" in sharding_strategy:
        num_shards_per_group = min(8, world_size)
    else:
        num_shards_per_group = world_size
    num_groups = world_size // num_shards_per_group
    for i in range(num_groups):
        start_rank = i * num_shards_per_group
        end_rank = (i + 1) * num_shards_per_group
        ranks = range(start_rank, end_rank)
        cpu_group = dist.new_group(ranks, backend="gloo")
        if rank in ranks:
            _MODEL_SHARD_CPU_GROUP = cpu_group
