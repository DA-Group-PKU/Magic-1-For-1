"""
Configuration utility functions
"""

import importlib
from typing import Any, Callable, List, Union
from omegaconf import DictConfig, ListConfig, OmegaConf

from .platform import get_region

OmegaConf.register_new_resolver("eval", eval)


def load_config(path: str, argv: List[str] = None) -> Union[DictConfig, ListConfig]:
    """
    Load a configuration. Will resolve inheritance.
    """
    config = OmegaConf.load(path)
    if argv is not None:
        config_argv = OmegaConf.from_dotlist(argv)
        config = OmegaConf.merge(config, config_argv)
    config = resolve_recursive(config, resolve_inheritance)
    config = resolve_recursive(config, resolve_region)
    return config


def resolve_recursive(
    config: Any,
    resolver: Callable[[Union[DictConfig, ListConfig]], Union[DictConfig, ListConfig]],
) -> Any:
    config = resolver(config)
    if isinstance(config, DictConfig):
        for k in config.keys():
            v = config.get(k)
            if isinstance(v, (DictConfig, ListConfig)):
                config[k] = resolve_recursive(v, resolver)
    if isinstance(config, ListConfig):
        for i in range(len(config)):
            v = config.get(i)
            if isinstance(v, (DictConfig, ListConfig)):
                config[i] = resolve_recursive(v, resolver)
    return config


def resolve_inheritance(config: Union[DictConfig, ListConfig]) -> Any:
    """
    Recursively resolve inheritance if the config contains:
    __inherit__: path/to/parent.yaml or a ListConfig of such paths.
    """
    if isinstance(config, DictConfig):
        inherit = config.pop("__inherit__", None)

        if inherit:
            inherit_list = inherit if isinstance(inherit, ListConfig) else [inherit]

            parent_config = None
            for parent_path in inherit_list:
                assert isinstance(parent_path, str)
                parent_config = (
                    load_config(parent_path)
                    if parent_config is None
                    else OmegaConf.merge(parent_config, load_config(parent_path))
                )

            if len(config.keys()) > 0:
                config = OmegaConf.merge(parent_config, config)
            else:
                config = parent_config
    return config


def resolve_region(config: Union[DictConfig, ListConfig]) -> Any:
    """
    Recursively resolve region if the config contains:
    __region__:
        cn: ...
        us: ...
    """
    if isinstance(config, DictConfig):
        regions = config.pop("__region__", None)
        region = get_region() or "cn"
        if regions:
            if region not in regions:
                raise ValueError("__region__ does not provide config for {region}")
            config = regions[region]
    return config


def import_item(path: str, name: str) -> Any:
    """
    Import a python item. Example: import_item("path.to.file", "MyClass") -> MyClass
    """
    return getattr(importlib.import_module(path), name)


def create_object(config: DictConfig) -> Any:
    """
    Create an object from config.
    The config is expected to contains the following:
    __object__:
      path: path.to.module
      name: MyClass
      args: as_config | as_params (default to as_config)
    """
    item = import_item(
        path=config.__object__.path,
        name=config.__object__.name,
    )
    args = config.__object__.get("args", "as_config")
    if args == "as_config":
        return item(config)
    if args == "as_params":
        config = OmegaConf.to_object(config)
        config.pop("__object__")
        return item(**config)
    raise NotImplementedError(f"Unknown args type: {args}")


def create_dataset(path: str, *args, **kwargs) -> Any:
    """
    Create a dataset. Requires the file to contain a "create_dataset" function.
    """
    return import_item(path, "create_dataset")(*args, **kwargs)


def resolve_load_model(config: Union[DictConfig, ListConfig]) -> Any:
    """
    Recursively resolve load model if the config contains:
    __load_model__:
        task: merlin_task_id
        name: model name
        steps: ...
    """
    from common.persistence.loader import load_model_from_task

    if isinstance(config, DictConfig):
        loaded_model_info = config.pop("__load_model__", None)
        if loaded_model_info:
            loaded_model = load_model_from_task(
                task=loaded_model_info.task,
                name=loaded_model_info.name,
                step=loaded_model_info.step,
                distributed=False,
            )
            loaded_model_config = loaded_model.config.load(distributed=False)

            loaded_config = OmegaConf.create(
                {"model": loaded_model_config, "checkpoint": loaded_model.states.path}
            )

            if len(config.keys()) > 0:
                config = OmegaConf.merge(loaded_config, config)
            else:
                config = loaded_model_config
    return config
