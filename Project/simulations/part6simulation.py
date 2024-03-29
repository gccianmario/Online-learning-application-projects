import numpy as np
from learners.CombWrapper import CombWrapper
from learners.GPUCB1_Learner import GPUCB1_Learner
from learners.SwGPUCB1_Learner import SwGPUCB1_Learner
from learners.CusumGPUCB1_Learner import CusumGPUCB1Learner
from learners.SwGTSLearner import SwGTSLearner
from learners.CusumGTSLearner import CusumGTSLearner
from learners.GTS_Learner import GTS_Learner
from simulations.Environment import Environment
from simulations.SimulationHandler import SimulationHandler
from entities.Utils import BanditNames
if __name__ == '__main__':
    """ @@@@ simulations SETUP @@@@ """
    experiments = 100
    days = 80
    N_user = 350  # reference for what alpha = 1 refers to
    reference_price = 4.0
    daily_budget = 50 * 6
    step_k = 5
    n_arms = 3*int(np.ceil(np.power(days * np.log(days), 0.25))) + 1

    bool_alpha_noise = True
    bool_n_noise = True
    printBasicDebug = False
    printKnapsackInfo = False
    boost_start = True
    boost_discount = 0.5  # boost discount wr to the highest reward
    boost_bias = daily_budget / 5  # ensure a positive reward when all pull 0

    """ These parameters change a lot the performance of the CUSUM based bandits !! """
    kwargs_cusum = {"samplesForRefPoint": 10,
                    "epsilon":            0.05,
                    "detectionThreshold": 200,  # np.log(days)*2 + 0.2*days
                    "explorationAlpha":   0.01}

    """ This parameter changes a lot the performance of the SW based bandits !! """
    window_size = int(np.sqrt(days) + 0.1 * days)

    kwargs_sw = {'window_size': window_size}

    """ @@@@ ---------------- @@@@ """

    sw_gpucb1_learner = CombWrapper(SwGPUCB1_Learner,
                                    5,
                                    n_arms,
                                    daily_budget,
                                    is_ucb = True,
                                    kwargs = kwargs_sw,
                                    is_gaussian = True)
    cusum_gpucb1_learner = CombWrapper(CusumGPUCB1Learner,
                                       5,
                                       n_arms,
                                       daily_budget,
                                       is_ucb = True,
                                       kwargs = kwargs_cusum,
                                       is_gaussian = True)

    sw_gts_learner = CombWrapper(SwGTSLearner,
                                 5,
                                 n_arms,
                                 daily_budget,
                                 is_ucb = False,
                                 kwargs = kwargs_sw,
                                 is_gaussian = True)

    cusum_gts_learner = CombWrapper(CusumGTSLearner,
                                    5,
                                    n_arms,
                                    daily_budget,
                                    is_ucb = False,
                                    kwargs = kwargs_cusum,
                                    is_gaussian = True)

    gts_learner = CombWrapper(GTS_Learner,
                              5,
                              n_arms,
                              daily_budget,
                              is_ucb = False,
                              is_gaussian = True)

    learners = [sw_gpucb1_learner, sw_gts_learner, cusum_gts_learner, cusum_gpucb1_learner, gts_learner]

    """ Number of users per phase """

    N_user_phases = [N_user, int(N_user * 0.5), int(N_user + 0.5 * N_user)]

    # 84 days -> 3 phases

    # first phase -> 1 april -> 30 april  30 days NORMAL CONDITIONS
    # second phase -> 1 maggio -> 28 maggio 28 days  HALF THE USERS
    # third phase -> 29 maggio -> 20 giugno 18 days  1.5 THE USERS -> SALES e.g

    n_phases = len(N_user_phases)

    phase_sizes = [30, 28, 22]

    """ Probability of users per phase """

    prob_users_phases = [[] for _ in range(n_phases)]

    for phase in range(n_phases):
        probs = abs(np.random.normal(size = 3))
        probs /= probs.sum()
        prob_users_phases[phase] = list(probs)

    non_stationary_args = {
        "phase_sizes": phase_sizes,
        "prob_users_phases": prob_users_phases,
        "num_users_phases": N_user_phases
    }

    simulationHandler = SimulationHandler(environmentConstructor = Environment,
                                          learners = learners,
                                          experiments = experiments,
                                          days = days,
                                          reference_price = reference_price,
                                          daily_budget = daily_budget,
                                          n_users = N_user,
                                          n_arms = n_arms,
                                          campaigns = 5,
                                          bool_alpha_noise = bool_alpha_noise,
                                          bool_n_noise = bool_n_noise,
                                          print_basic_debug = printBasicDebug,
                                          print_knapsack_info = printKnapsackInfo,
                                          step_k = step_k,
                                          non_stationary_args = non_stationary_args,
                                          clairvoyant_type = 'aggregated',
                                          boost_start = boost_start,
                                          boost_bias = boost_bias,
                                          boost_discount = boost_discount,
                                          plot_regressor_progress = None,
                                          simulation_name='Part6Simulation',
                                          learner_profit_plot = BanditNames.SwGTSLearner.name,
                                          plot_confidence_intervals = False
                                          )

    simulationHandler.run_simulation()
