import numpy as np
import warnings
from sklearn.exceptions import ConvergenceWarning
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel as C
from learners.Learner import Learner
from entities.Utils import BanditNames

class GPTS_Learner(Learner):
    def __init__(self, arms, n_campaigns, prior_mean, prior_sigma=1):  # arms are the budgets (e.g 0,10,20...)
        super().__init__(len(arms))
        self.n_arms = len(arms)
        self.arms = arms
        self.prior_mean = prior_mean
        self.prior_sigma = prior_sigma
        self.means = np.ones(self.n_arms) * prior_mean      # cannot be controlled directly
        self.sigmas = np.ones(self.n_arms) * prior_sigma    # cannot be controlled directly
        self.pulled_arms = []
        self.bandit_name = BanditNames.GPTS_Learner.name
        self.needs_boost = True

        alpha = 0.5
        theta = 1  # regulates how wide the uncertainty area is (control exploration)
        l = 1  # regulate how close 2 points should be to be similar
        kernel = C(theta, (1e-3, 1e3)) * RBF(l, (1e-3, 1e3))  # to be adjusted
        self.kernel = kernel
        self.alpha = alpha
        self.gp = GaussianProcessRegressor(kernel=kernel,
                                           alpha=alpha**2,
                                           normalize_y=True,
                                           n_restarts_optimizer=9)

    def update_observations(self, pulled_arm, reward):
        super().update_observations(pulled_arm, reward)
        self.pulled_arms.append(self.arms[pulled_arm])

    def update_model(self):
        x = np.atleast_2d(self.pulled_arms).T
        y = self.collected_rewards
        warnings.simplefilter(action='ignore', category=ConvergenceWarning)
        self.gp.fit(x, y)
        self.means, self.sigmas = self.gp.predict(
            np.atleast_2d(self.arms).T,
            return_std=True)

    def update(self, pulled_super_arm, rewards):
        self.t += 1
        self.update_observations(pulled_super_arm, rewards)
        self.update_model()

    def pull_arm(self) -> np.array:
        """ Pull an arm and the set of value of all the arms"""
        arms_value = np.random.normal(self.means, self.sigmas)
        idx = np.argmax(arms_value)
        return idx, arms_value

    def reset(self):
        super(GPTS_Learner, self).reset()

        self.means = np.ones(self.n_arms) * self.prior_mean
        self.sigmas = np.ones(self.n_arms) * self.prior_sigma

        self.gp = GaussianProcessRegressor(kernel=self.kernel,
                                           alpha=self.alpha ** 2,
                                           normalize_y=True,
                                           n_restarts_optimizer=9)

        self.pulled_arms = []
