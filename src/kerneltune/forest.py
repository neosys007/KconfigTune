# -*- coding:utf-8 -*-
# Author: xiansong@nj.iscas.ac.cn

import numpy as np
from sklearn.ensemble import RandomForestRegressor as _sk_RandomForestRegressor


class RandomForestRegressor(_sk_RandomForestRegressor):
    def __init__(self,
                 n_estimators=10,
                 max_depth=None,
                 min_samples_split=2,
                 min_samples_leaf=1,
                 min_weight_fraction_leaf=0.0,
                 max_features=1.0,
                 max_leaf_nodes=None,
                 min_impurity_decrease=0.,
                 bootstrap=True,
                 oob_score=False,
                 n_jobs=1,
                 random_state=None,
                 verbose=0,
                 warm_start=False,
                 min_variance=0.0):
        super(RandomForestRegressor, self).__init__(
            n_estimators=n_estimators,
            max_depth=max_depth,
            min_samples_split=min_samples_split,
            min_samples_leaf=min_samples_leaf,
            min_weight_fraction_leaf=min_weight_fraction_leaf,
            max_features=max_features,
            max_leaf_nodes=max_leaf_nodes,
            min_impurity_decrease=min_impurity_decrease,
            bootstrap=bootstrap,
            oob_score=oob_score,
            n_jobs=n_jobs,
            random_state=random_state,
            verbose=verbose,
            warm_start=warm_start)

        self.min_variance = min_variance

    def predict(self, X):
        mean = super(RandomForestRegressor, self).predict(X)
        std = np.zeros(len(X))
        for tree in self.estimators_:
            var_tree = tree.tree_.impurity[tree.apply(X)]
            var_tree[var_tree < self.min_variance] = self.min_variance
            mean_tree = tree.predict(X)
            std += var_tree + mean_tree ** 2

        std /= len(self.estimators_)
        std -= mean ** 2.0
        std[std < 0.0] = 0.0
        std = std ** 0.5
        return mean, std

    def feature_importances(self):
        return self.feature_importances_