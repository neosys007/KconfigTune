# -*- coding：utf-8 -*-
import os
import json
from ConfigSpace.read_and_write import json as csjson
from ConfigSpace import ConfigurationSpace, UniformFloatHyperparameter, UniformIntegerHyperparameter

from .logging import get_logger


logger = get_logger(__name__)


def check_default_parameters(keys, default_keys, force=False):
    new_keys = []
    for key in keys:
        if key not in default_keys:
            if force:
                logger.warning(f"{key} is not included in the default parameter list.")
            else:
                raise ValueError(f"{key} is not included in the default parameter list.")
        else:
            new_keys.append(key)
    if force:
        return new_keys
    return keys


def remove_parameter_from_history(observations: list, shared_parameters):
    new_observations = []
    for o in observations:
        configuration = o.get("configuration")
        for key in shared_parameters:
            if configuration[key] != shared_parameters[key]:
                break

        for key in shared_parameters:
            del configuration[key]

        o["configuration"] = configuration
        new_observations.append(o)

    return new_observations


def extend_parameter_to_history(observations, shared_parameters):
    new_observations = []
    for o in observations:
        configuration = o.get("configuration")
        configuration.update(shared_parameters)
        o["configuration"] = configuration
        new_observations.append(o)
    return new_observations


def remove_illegal_boundaries(observations, current_configspace):
    bound_dict = {}
    type_dict = {}
    for k, p in current_configspace.get_hyperparameters_dict().items():
        if isinstance(p, UniformIntegerHyperparameter):
            bound_dict[k] = (p.lower, p.upper)
            type_dict[k] = "uniform_int"
        elif isinstance(p, UniformFloatHyperparameter):
            bound_dict[k] = (p.lower, p.upper)
            type_dict[k] = "uniform_float"
        else:
            bound_dict[k] = p.choices
            type_dict[k] = "categorical"

    logger.info(f"Current configuration space:\n\tboundaries: {bound_dict}\n\ttypes: {type_dict}")

    tmp = []
    new_observations = []
    for o in observations:
        config = o.get("configuration")
        illegal = False
        for key, bounds in bound_dict.items():
            val = config[key]
            typ = type_dict[key]
            if typ == "categorical":
                if val not in bounds:
                    logger.debug(f"Configuration {config} contains an illegal value for `{key}={val}`")
                    illegal = True
                    break
            elif typ == "uniform_float" or typ == "uniform_int":
                if val < bounds[0] or val > bounds[1]:
                    logger.debug(f"Configuration {config} contains an illegal value for `{key}={val}`")
                    illegal = True
                    break

        if illegal:
            logger.info(f"Remove illegal configuration {config}")
        else:
            if config not in tmp:
                new_observations.append(o)
                tmp.append(config)

    del tmp

    return new_observations


def alignment_configspace(filepath: str, current_configspace: ConfigurationSpace,
                          shared_default_parameters: dict = None):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f'Filepath not found: {filepath}')

    with open(filepath, "r", encoding="utf-8") as fp:
        data = json.load(fp)

    if shared_default_parameters is None:
        shared_default_parameters = data.get("shared_default_parameters", {})

    history_configspace = json.dumps(data.pop("configspace"))
    history_configspace = csjson.read(history_configspace)
    observations = data.pop("observations")
    logger.info(f"History {history_configspace}")
    logger.info(f"Current {current_configspace}")
    current_keys = set(current_configspace.keys())
    history_keys = set(history_configspace.keys())
    if current_keys == history_keys:
        logger.info("The configuration space key is identical.")
        observations = remove_illegal_boundaries(observations, current_configspace)
    else:
        if current_keys.issubset(history_keys):
            remove_keys = history_keys - current_keys
            remove_keys = check_default_parameters(remove_keys, shared_default_parameters)
            shared_parameters = {k: shared_default_parameters[k] for k in remove_keys}
            logger.info(f"Remove parameters: {shared_parameters}")
            observations = remove_parameter_from_history(observations, shared_parameters)
        elif history_keys.issubset(current_keys):
            extend_keys = current_keys - history_keys
            shared_parameters = {k: shared_default_parameters[k] for k in extend_keys}
            logger.info(f"Extend parameters: {shared_parameters}")
            observations = extend_parameter_to_history(observations, shared_parameters)
        else:
            shared_keys = current_keys & history_keys
            if shared_keys:
                remove_keys = history_keys - shared_keys
                remove_parameters = {k: shared_default_parameters[k] for k in remove_keys}
                logger.info(f"Remove parameters: {remove_parameters}")
                observations = remove_parameter_from_history(observations, remove_parameters)
                extend_keys = current_keys - shared_keys
                extend_parameters = {k: shared_default_parameters[k] for k in extend_keys}
                logger.info(f"Extend parameters: {extend_parameters}")
                observations = extend_parameter_to_history(observations, extend_parameters)
            else:
                raise ValueError(f"Both configuration spaces do not contain the same parameters:"
                                 f" {current_keys} and {history_keys}")

        observations = remove_illegal_boundaries(observations, current_configspace)

    data["observations"] = observations
    current_configspace = csjson.write(current_configspace)
    current_configspace = json.loads(current_configspace)
    data["configspace"] = current_configspace

    save_path = filepath.replace('.json', '_alignment.json')
    with open(save_path, "w", encoding="utf-8") as fp:
        json.dump(data, fp, indent=4)

    return data




