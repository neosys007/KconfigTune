# -*- coding: utf-8 -*-
# Author: xiansong@nj.iscas.ac.cn
import os
import json
import numpy as np
from ConfigSpace import Configuration
from ConfigSpace.read_and_write import json as csjson

from .util import transform_dict_to_configuration
from .util import StatusCode
from .logging import get_logger


logger = get_logger(__name__)


class Observation(object):
    def __init__(self, configuration, performance=np.nan, runtime=np.nan, state=StatusCode.Success):
        self.state = state
        self.configuration = configuration
        self.performance = performance
        self.runtime = runtime

    def __repr__(self):
        info = {
            "configuration": self.configuration.get_dictionary(),
            "performance": self.performance,
            "runtime": self.runtime if self.runtime else None,
            "status": self.state,
        }

        return "\n" + json.dumps(info, indent=4)

    def to_dict(self):
        info = {
            "configuration": self.configuration.get_dictionary(),
            "performance": self.performance,
            "state": self.state,
        }
        if self.runtime is not None:
            info["runtime"] = self.runtime
        return info

    @classmethod
    def from_dict(cls, values, configspace):
        configuration = values.get("configuration")
        if isinstance(configuration, dict):
            values["configuration"] = transform_dict_to_configuration(configuration, configspace)
        else:
            assert isinstance(configuration, Configuration), "configuration must be a `dict` or `Configuration`."

        observation = cls(**values)
        return observation


class History(object):
    def __init__(self, configspace):
        self.configspace = configspace
        self.observations = []

    def __len__(self):
        return len(self.observations)

    def update(self, observation, meta: str = "") -> None:
        if isinstance(observation, Observation):
            observation = [observation]
        for o in observation:
            if not self.in_history(o.configuration):
                self.observations.append(o)
                logger.debug(f"update{meta} observation: {o}")
            else:
                logger.info(f"configuration already exist: {o.configuration.get_dictionary()}")

    def optimized_observations(self):
        objectives = np.asarray(self.performances)
        min_value = np.nanmin(objectives)
        best_index = np.where(objectives == min_value)[0]
        return [self.observations[i] for i in best_index]

    def feasible_mask(self):
        mask = [s == StatusCode.Success for s in self.status]
        mask = np.asarray(mask, dtype=bool)
        return mask

    def transform(self, transform_time=False):
        mask = self.feasible_mask()
        performances = np.asarray(self.performances, dtype=np.float64)
        performances[~mask] = np.nanmax(performances)
        if transform_time:
            runtimes = np.asarray(self.runtimes)
            max_value = np.nanmax(runtimes)
            runtimes[~mask] = max_value
            runtimes = np.log(runtimes)
            return performances, runtimes

        return performances

    def in_history(self, configuration):
        if configuration in self.configurations:
            return True
        return False

    def optimal_result(self):
        optimal = self.optimized_observations()
        if len(optimal) > 0:
            optimal = optimal[0].to_dict()
        return optimal

    @property
    def best_perf(self):
        optimal = self.optimal_result()
        return optimal.get("performance")

    @property
    def configurations(self):
        return [o.configuration for o in self.observations]

    @property
    def runtimes(self):
        return [o.runtime for o in self.observations]

    @property
    def performances(self):
        return [o.performance for o in self.observations]

    @property
    def status(self):
        return [o.state for o in self.observations]

    def save(self, filepath: str, shared_default_parameters: dict = None):
        filepath = os.path.abspath(filepath)
        filedirs, filename = os.path.split(filepath)
        if not os.path.exists(filedirs):
            logger.info(f'Creating directory to save history: {filedirs}')
            os.makedirs(filedirs, exist_ok=True)
        configspace = csjson.write(self.configspace)
        configspace = json.loads(configspace)
        task = {
            "configspace": configspace,
            "optimal_solution": [o.to_dict() for o in self.optimized_observations()],
            "observations": [o.to_dict() for o in self.observations]
        }

        if shared_default_parameters is not None:
            task["shared_default_parameters"] = shared_default_parameters

        with open(filepath, "w", encoding="utf-8") as fp:
            json.dump(task, fp, indent=4)

        logger.info(f"Save history to {filename}")

    @classmethod
    def load(cls, filepath: str):
        if not os.path.exists(filepath):
            raise FileNotFoundError(f'Filepath not found: {filepath}')

        with open(filepath, "r", encoding="utf-8") as fp:
            data = json.load(fp)

        configspace = json.dumps(data.pop("configspace"))
        configspace = csjson.read(configspace)
        logger.info(f"load history:  {configspace}")
        observations = [Observation.from_dict(o, configspace) for o in data.pop("observations")]
        data.pop("optimal_solution")
        if data.get("shared_default_parameters") is not None:
            data.pop("shared_default_parameters")
        data["configspace"] = configspace
        history = cls(**data)
        history.update(observations, meta=" history")
        logger.info(f"Load history from {filepath}.  "
                    f"Total number of configurations: {len(history.observations)}")
        return history
