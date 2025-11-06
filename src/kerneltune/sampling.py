# -*- coding:utf-8 -*-
# Author: xiansong@nj.iscas.ac.cn

import numpy as np
from sklearn.utils import check_random_state


class RandomSearch(object):
    def __init__(self, acq_func, configspace, n_sample=10000, random_state=None):
        self.configspace = configspace
        self.acq_func = acq_func
        self.n_sample = n_sample
        self.random_state = check_random_state(random_state)

    def consort(self):
        configurations = []
        for sample in self._sort_acquisition():
            configurations.append(sample[1])
        return configurations

    def _sort_acquisition(self):
        configurations = self.configspace.sample_configuration(self.n_sample)
        configurations = list(set(configurations))
        values = self.acq_func(configurations)
        random = self.random_state.rand(len(values))
        indices = np.lexsort((random.flatten(), values.flatten()))
        return [(values[idx], configurations[idx]) for idx in indices]