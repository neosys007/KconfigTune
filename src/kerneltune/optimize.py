# -*- coding:utf-8 -*-
# Author: xiansong@nj.iscas.ac.cn
import os
from sklearn.utils import check_random_state

from .forest import RandomForestRegressor
from .acquisition import Acquisition
from .history import History
from .sampling import RandomSearch
from .util import convert_configurations_to_array
from .logging import get_logger


logger = get_logger(__name__)


class BayesianOptimizer:
    def __init__(self, configspace, n_initial_points=10, random_state=None, history=None):
        self.n_initial_points = n_initial_points
        self.random_state = check_random_state(random_state)
        self.configspace = configspace
        self.configspace.seed(self.random_state.randint(100000000))

        self.history = history
        if not isinstance(history, History):
            self.history = History(self.configspace)

        self.space_size = int(self.configspace.estimate_size())
        self.initial_configurations = self.configspace.sample_configuration(self.n_initial_points)
        self.n_initial_points = len(self.initial_configurations)

        self.model = None
        self.time_model = None
        self.acquisition = None
        self.optimizer = None
        self.run_status = 0
        self._build()

    def initial_history(self, filename):
        self.history = History(self.configspace)
        if filename is not None and os.path.exists(filename):
            logger.info(f"load initial configurations from {filename}")
            self.history.load(filename)
        else:
            self.initial_configurations = self.configspace.sample_configuration(self.n_initial_points)
            self.n_initial_points = len(self.initial_configurations)

    def _build(self):
        self.model = RandomForestRegressor(n_estimators=20, random_state=self.random_state)
        self.time_model = RandomForestRegressor(n_estimators=20, random_state=self.random_state)
        self.acquisition = Acquisition(self.model, self.time_model, xi=0.001,  best_perf=0.0)
        self.optimizer = RandomSearch(
            acq_func=self.acquisition,
            configspace=self.configspace,
            random_state=self.random_state,
            n_sample=min(self.space_size, 50000)
        )

    def update(self, observation):
        if not self.history.in_history(observation.configuration):
            return self.history.update(observation)
        logger.info(f"Repetitive update observation: {observation}")

    def suggest(self):
        n_evaluated = len(self.history)
        if n_evaluated == 0:
            return self.configspace.get_default_configuration()

        if n_evaluated < self.n_initial_points:
            return self.initial_configurations[n_evaluated]

        self.train(self.history)
        self.acquisition.update(model=self.model,
                                time_model=self.time_model,
                                best_perf=self.history.best_perf,
                                n_evaluated=n_evaluated)

        configurations = self.optimizer.consort()
        for configuration in configurations:
            if configuration not in self.history.configurations:
                return configuration

        return self.configspace.sample_configuration()

    def train(self, history):
        performances, elapsedtimes = history.transform(transform_time=True)
        configurations = convert_configurations_to_array(history.configurations)
        self.model.fit(configurations, performances)
        self.time_model.fit(configurations, elapsedtimes)

    def optimized_result(self):
        optimal = self.history.optimized_observations()
        if len(optimal) > 0:
            optimal = optimal[0].to_dict()
        return optimal

    def importances(self):
        value = self.model.feature_importances_
        key = self.configspace.get_hyperparameter_names()
        importances = sorted(zip(key, value), key=lambda x: x[1], reverse=True)
        return dict(importances)