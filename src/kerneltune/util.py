# -*- coding:utf-8 -*-
# Author: xiansong@nj.iscas.ac.cn

import numpy as np
from ConfigSpace import Configuration
from ConfigSpace import ConfigurationSpace
from ConfigSpace import UniformIntegerHyperparameter
from ConfigSpace import UniformFloatHyperparameter
from ConfigSpace import CategoricalHyperparameter


# STATE CODE
class StatusCode:
    Success = 100
    Failed = 101
    Timeout = 102
    Closed = 103
    EarlyStop = 104


class ParameterType:
    Integer = "int"
    Float = "float"
    Categorical = "cate"


def generate_configspace(configuration):
    space = ConfigurationSpace()
    for name, param in configuration.items():
        ptype = param.get("type")
        if ptype in [ParameterType.Float, ParameterType.Integer]:
            args = dict()
            if param.get("default", None):
                args['default_value'] = param.get("default")
            if param.get("step", None):
                args['q'] = param.get("step")
            lower, upper = param.get("bound")
            if ptype == ParameterType.Float:
                parameter = UniformFloatHyperparameter(name, lower, upper, **args)
            else:
                parameter = UniformIntegerHyperparameter(name, lower, upper, **args)
        elif ptype == ParameterType.Categorical:
            args = dict()
            if param.get("default", None):
                args['default_value'] = param.get("default")
            choices = param.get("choices")
            parameter = CategoricalHyperparameter(name, choices, **args)
        else:
            raise ValueError(f"Parameter type {ptype} not supported!")
        space.add_hyperparameter(parameter)
    return space


def convert_configurations_to_array(configurations):
    vectors = [c.get_array() for c in configurations]
    vectors = np.array(vectors, dtype=np.float64)
    configspace = configurations[0].configuration_space
    for hp in configspace.get_hyperparameters():
        default = hp.normalized_default_value
        idx = configspace.get_idx_by_hyperparameter_name(hp.name)
        nonfinite_mask = ~np.isfinite(vectors[:, idx])
        vectors[nonfinite_mask, idx] = default

    return vectors


def transform_dict_to_configuration(values: dict, configspace: ConfigurationSpace):
    config = Configuration(configuration_space=configspace, values=values)
    return Configuration(configuration_space=config.configuration_space, values=config.get_dictionary())