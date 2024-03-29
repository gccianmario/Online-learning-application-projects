import os
import copy
import seaborn as sns
from typing import Type
from typing import Union
from typing import List
import numpy as np
from entities import Utils as util
import matplotlib.pyplot as plt
from learners.CombWrapper import CombWrapper
from tqdm import tqdm
import matplotlib
import json
from simulations.Environment import Environment

matplotlib.use("TkAgg")


class SimulationHandler:

    def __init__(self,
                 environmentConstructor: Type[Environment],
                 learners: List['CombWrapper'],
                 experiments: int,
                 days: int,
                 reference_price: Union[float, int],
                 daily_budget: Union[float, int],
                 n_arms: int,
                 n_users: int,
                 bool_alpha_noise: bool,
                 bool_n_noise: bool,
                 print_basic_debug: bool,
                 print_knapsack_info: bool,
                 campaigns: int,
                 step_k: int,
                 non_stationary_args: dict = None,
                 is_unknown_graph: bool = False,
                 clairvoyant_type: str = 'aggregated',
                 boost_start: bool = False,
                 boost_discount: float = 0.5,
                 boost_bias: float = -1.0,
                 plot_regressor_progress = None,
                 save_results_to_file = True,
                 simulation_name: str = 'simulation',
                 learner_profit_plot = None,
                 plot_confidence_intervals = True):
        self.environmentConstructor = environmentConstructor
        self.environment = self.environmentConstructor()
        self.learners = learners
        self.learners_rewards_per_experiment = [[] for _ in range(len(self.learners))]
        self.learners_rewards_per_day = [[] for _ in range(len(self.learners))]
        self.super_arms = []

        self.clairvoyant_rewards_per_experiment_t1 = []
        self.clairvoyant_rewards_per_experiment_t2 = []
        self.clairvoyant_rewards_per_day_t1 = []
        self.clairvoyant_rewards_per_day_t2 = []

        self.avg_clairvoyant_profit_functions_t1 = []
        self.avg_clairvoyant_profit_functions_t2 = []

        self.buds = []
        self.campaigns = campaigns

        self.days = days
        self.experiments = experiments
        self.reference_price = reference_price
        self.daily_budget = daily_budget
        self.n_arms = n_arms
        self.bool_alpha_noise = bool_alpha_noise
        self.bool_n_noise = bool_n_noise
        self.print_basic_debug = print_basic_debug
        self.print_knapsack_info = print_knapsack_info
        self.non_stationary_env = False
        self.n_users = n_users
        self.is_unknown_graph = is_unknown_graph
        self.clairvoyant_type = clairvoyant_type
        self.step_k = step_k
        self.plot_regressor_progress = plot_regressor_progress
        self.save_results_to_file = save_results_to_file
        self.plot_confidence_intervals = plot_confidence_intervals

        if save_results_to_file:
            if not os.path.isdir("../results"):
                os.makedirs("../results")
            os.chdir("../results")



        self.uniform_allocation_profits = []

        self.boost_start = boost_start
        self.boost_discount = boost_discount
        campaigns = campaigns * self.n_users if self.clairvoyant_type == 'disaggregated' else campaigns  # to generalize !!
        self.boost_bias = boost_bias if boost_bias >= 0.0 else self.daily_budget / campaigns

        self.simulation_name = simulation_name
        self.figsize = (16, 10)
        self.learner_profit_plot = learner_profit_plot

        if non_stationary_args and isinstance(non_stationary_args, dict):
            self.phase_sizes = non_stationary_args['phase_sizes']
            self.num_users_phases = non_stationary_args['num_users_phases']
            self.prob_users_phases = non_stationary_args['prob_users_phases']
            self.non_stationary_env = True

    def __set_budgets_env(self, budgets):
        for i, b in enumerate(budgets):
            self.environment.set_campaign_budget(i, b)

    def find_learner_idx(self, name) -> int:
        if isinstance(name, str):
            for idx, l in enumerate(self.learners):
                if l.bandit_name == name:
                    return idx
        return -1

    def run_simulation(self):

        self.learners_rewards_per_experiment = [[] for _ in range(len(self.learners))]
        self.clairvoyant_rewards_per_experiment_t1 = []

        self.avg_clairvoyant_profit_functions_t1 = [[] for _ in range(self.campaigns)]
        self.avg_clairvoyant_profit_functions_t2 = [[] for _ in range(self.campaigns * self.n_users)]

        if self.clairvoyant_type == 'disaggregated':
            self.avg_clairvoyant_profit_functions_t1 = [[] for _ in range(self.campaigns * self.n_users)]

        self.learner_profit_functions_per_experiment = [[[] for _ in range(self.campaigns)] for _ in range(len(self.learners))]
        self.learner_profit_functions_per_experiment_std = [[[] for _ in range(self.campaigns)] for _ in range(len(self.learners))]

        if self.clairvoyant_type == 'both':
            self.clairvoyant_rewards_per_experiment_t2 = []

        if self.plot_regressor_progress:
            img, axss = plt.subplots(nrows = 2, ncols = 3, figsize = self.figsize)
            axs = axss.flatten()
            plt.subplots_adjust(left = 0.05, right = 0.95, hspace = 0.6, top = 0.9, wspace = 0.4, bottom = 0.1)

            for ax in axs:
                ax.grid(alpha = 0.2)

            sns.set_style("ticks")
            sns.despine()
            sns.set_context('notebook')

            learner_to_observe = None

            for idx, learner in enumerate(self.learners):
                if learner.bandit_name == self.plot_regressor_progress:
                    learner_to_observe = learner
                    idx_learner_to_observe = idx
                    break

            colors = util.get_colors()

        for experiment in range(self.experiments):

            if experiment > 0:
                util.clear_output()

            if True:
                print(f"\n***** EXPERIMENT {experiment + 1} *****")

            self.super_arms = []

            for index, learner in enumerate(self.learners):
                learner.reset()
                self.super_arms.append(learner.pull_super_arm())

            self.learners_rewards_per_day = [[] for _ in range(len(self.learners))]

            self.clairvoyant_rewards_per_day_t1 = []

            if self.clairvoyant_type == 'both':
                self.clairvoyant_rewards_per_day_t2 = []

            self.learners_rewards_per_day = [[] for _ in range(len(self.learners))]

            if self.is_unknown_graph:
                #   **** MONTE CARLO EXECUTION BEFORE EXPERIMENT ITERATION ****
                users, products, campaigns, allocated_budget, prob_users, real_graphs = self.environment.get_core_entities()
                self.real_graphs = copy.deepcopy(real_graphs)
                estimated_fully_conn_graphs, estimated_2_neighs_graphs, true_2_neighs_graphs = self.environment.run_graph_estimate()
                self.estimated_fully_conn_graphs = estimated_fully_conn_graphs
                #   ************************************************

            # -- Day Loop --
            for day in tqdm(range(self.days)):

                if self.is_unknown_graph:
                    self.environment.set_user_graphs(self.real_graphs)  # set real real_graphs for clavoyrant algorithm

                if self.non_stationary_env:
                    current_phase = day % len(self.phase_sizes)
                    self.n_users = self.num_users_phases[current_phase]
                    self.environment.prob_users = self.prob_users_phases[current_phase]

                if self.print_basic_debug:
                    print(f"\n***** DAY {day + 1} *****")

                users, products, campaigns, allocated_budget, prob_users, _ = self.environment.get_core_entities()

                sim_obj = self.environment.play_one_day(self.n_users, self.reference_price, self.daily_budget,
                                                        self.step_k,
                                                        self.bool_alpha_noise,
                                                        self.bool_n_noise)  # object with all the day info

                if self.clairvoyant_type == 'both':

                    # AGGREGATED
                    self.clairvoyant_rewards_per_day_t1.append(sim_obj["reward_k_agg"])

                    for idx, r in enumerate(sim_obj["rewards_agg"]):
                        if len(self.avg_clairvoyant_profit_functions_t1[idx]) == 0:
                            self.avg_clairvoyant_profit_functions_t1[idx].append(r)
                        else:
                            self.avg_clairvoyant_profit_functions_t1[idx] = (self.avg_clairvoyant_profit_functions_t1[
                                                                                 idx] * day + r) / (day + 1)

                    # DISAGGREGATED
                    self.clairvoyant_rewards_per_day_t2.append(sim_obj["reward_k_disagg"])

                    for idx, r in enumerate(sim_obj["rewards_disagg"]):
                        if len(self.avg_clairvoyant_profit_functions_t2[idx]) == 0:
                            self.avg_clairvoyant_profit_functions_t2[idx].append(r)
                        else:

                            self.avg_clairvoyant_profit_functions_t2[idx] = (self.avg_clairvoyant_profit_functions_t2[
                                                                                 idx] * day + r) / (day + 1)

                else:
                    reward_k = sim_obj["reward_k_agg"] if self.clairvoyant_type == 'aggregated' else sim_obj[
                        "reward_k_disagg"]
                    self.clairvoyant_rewards_per_day_t1.append(reward_k)

                    reward = sim_obj["rewards_agg"] if self.clairvoyant_type == 'aggregated' else sim_obj[
                        "rewards_disagg"]

                    for idx, r in enumerate(reward):
                        if len(self.avg_clairvoyant_profit_functions_t1[idx]) == 0:
                            self.avg_clairvoyant_profit_functions_t1[idx].append(r)
                        else:

                            self.avg_clairvoyant_profit_functions_t1[idx] = (self.avg_clairvoyant_profit_functions_t1[
                                                                                 idx] * day + r) / (
                                                                                    day + 1)
                # -----------------------------------------------------------------

                if self.is_unknown_graph:
                    """print("Estimated Graph setted")"""
                    self.environment.set_user_graphs(
                            self.estimated_fully_conn_graphs)  # set real real_graphs for clavoyrant algorithm

                # --- uniform allocation benchmark ----

                uniform_allocation = [self.daily_budget / 5 for _ in range(5)]
                sim_obj_2 = self.environment.replicate_last_day(uniform_allocation,
                                                                self.n_users,
                                                                self.reference_price,
                                                                self.bool_n_noise,
                                                                self.bool_n_noise)
                self.uniform_allocation_profits.append(np.sum(sim_obj_2["learner_rewards"]))

                # ------

                for learnerIdx, learner in enumerate(self.learners):
                    # update with data from today for tomorrow
                    super_arm = self.super_arms[learnerIdx]

                    # BOOST (Random exploration) DONE ONLY TO LEARNERS USING GP REGRESSOR
                    if self.boost_start and learner.needs_boost and day < 4:
                        idx = np.random.choice(len(learner.arms) - 1, 5, replace = True)
                        loop = 0
                        while np.sum(np.array(learner.arms)[idx]) >= self.daily_budget:
                            idx = np.random.choice(len(learner.arms) - 1 - loop, 5, replace = True)
                            loop += 1
                        # force random exploration
                        super_arm = np.array(learner.arms)[idx]

                    sim_obj_2 = self.environment.replicate_last_day(super_arm,
                                                                    self.n_users,
                                                                    self.reference_price,
                                                                    self.bool_n_noise,
                                                                    self.bool_n_noise)
                    profit_env = sim_obj_2["profit"]
                    learner_rewards = sim_obj_2["learner_rewards"]
                    net_profit_learner = np.sum(learner_rewards)
                    learner.update_observations(super_arm, learner_rewards)

                    # solve comb problem for tomorrow
                    self.super_arms[learnerIdx] = learner.pull_super_arm()

                    self.learners_rewards_per_day[learnerIdx].append(net_profit_learner)

                    self.buds = sim_obj["k_budgets"]

                    mean, std = learner.get_gp_data()

                    for i, m in enumerate(mean):

                        if len(self.learner_profit_functions_per_experiment[learnerIdx][i]) == 0:
                            self.learner_profit_functions_per_experiment[learnerIdx][i].append(m)
                            self.learner_profit_functions_per_experiment_std[learnerIdx][i].append(std[i])
                        else:
                            self.learner_profit_functions_per_experiment[learnerIdx][i] = (
                                                                                                  self.learner_profit_functions_per_experiment[
                                                                                                      learnerIdx][
                                                                                                      i] * day + m) / (
                                                                                                  day + 1)

                            self.learner_profit_functions_per_experiment_std[learnerIdx][i] = (
                                                                                                      self.learner_profit_functions_per_experiment_std[
                                                                                                          learnerIdx][
                                                                                                          i] * day +
                                                                                                      std[i]) / (
                                                                                                      day + 1)

                if self.plot_regressor_progress and learner_to_observe:
                    axs[5].cla()
                    x = sim_obj["k_budgets"]
                    x2 = learner_to_observe.arms
                    for i, rw in enumerate(sim_obj["rewards_agg"]):
                        axs[i].cla()
                        axs[i].set_xlabel("budget")
                        axs[i].set_ylabel("profit")
                        axs[i].plot(x, rw, colors[-1], label = 'clairvoyant profit', alpha = 0.5)
                        # axs[i].plot(x2, comb_learner.last_knapsack_reward[i])
                        mean, std = learner_to_observe.get_gp_data()
                        # print(std[0])
                        # print(mean[0][0])
                        axs[i].plot(x2, mean[i], colors[i], label = 'estimated profit', alpha = 0.5)
                        axs[i].fill_between(
                                np.array(x2).ravel(),
                                mean[i] - 1.96 * std[i],
                                mean[i] + 1.96 * std[i],
                                alpha = 0.1,
                                label = r"95% confidence interval",
                                color = colors[i]
                        )

                        axs[i].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                                      ncol = 2, mode = "expand", borderaxespad = 0.)

                        axs[i].set_title('Profit curve - Campaign ' + str(i + 1), y = 1.0, pad = 43)

                    d = np.linspace(0, len(self.clairvoyant_rewards_per_day_t1),
                                    len(self.clairvoyant_rewards_per_day_t1))
                    axs[5].set_xlabel("days")
                    axs[5].set_ylabel("reward")
                    axs[5].plot(d, self.clairvoyant_rewards_per_day_t1, colors[-1], label = "clairvoyant reward",
                                alpha = 0.5)
                    axs[5].plot(d, self.learners_rewards_per_day[idx_learner_to_observe], colors[-2],
                                label = "bandit reward", alpha = 0.5)
                    axs[5].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                                  ncol = 2, mode = "expand", borderaxespad = 0.)

                    axs[5].set_title('Reward', y = 1.0, pad = 28)

                    # axs[5].plot(d, rewards_disaggregated)
                    plt.pause(0.02)  # no need for this,

            self.clairvoyant_rewards_per_experiment_t1.append(self.clairvoyant_rewards_per_day_t1)

            if self.clairvoyant_type == 'both':
                self.clairvoyant_rewards_per_experiment_t2.append(self.clairvoyant_rewards_per_day_t2)

            for learnerIdx in range(len(self.learners)):
                self.learners_rewards_per_experiment[learnerIdx].append(self.learners_rewards_per_day[learnerIdx])

        # self.__plot_results(sns_style = 'white') # looks nice

        # self.__plot_results(sns_style = 'black') # looks nice but i do not it like that much

        if self.learner_profit_plot:

            id = self.find_learner_idx(self.learner_profit_plot)

            if id >= 0:
                colors = util.get_colors(type = 2)

                img, axss = plt.subplots(nrows = 2, ncols = 3, figsize = (20, 15))
                img.suptitle(self.learners[id].bandit_name + " profit curve")
                axs = axss.flatten()
                plt.subplots_adjust(left = 0.05, right = 0.95, hspace = 0.6, top = 0.85, wspace = 0.4, bottom = 0.1)

                for ax in axs:
                    ax.grid(alpha = 0.2)
                    sns.despine(ax = ax, offset = 5, trim = False)

                sns.set_style("ticks")
                sns.set_context('notebook')

                for i, rw in enumerate(self.avg_clairvoyant_profit_functions_t1):
                    x = self.buds
                    axs[i].set_xlabel("budget")
                    axs[i].set_ylabel("profit")
                    axs[i].plot(x, rw[0], colors.pop(), label = 'clairvoyant profit', alpha = 0.5)
                    x2 = self.learners[id].arms
                    mean = self.learner_profit_functions_per_experiment[id][i][0]
                    std = self.learner_profit_functions_per_experiment_std[id][i][0]
                    c = colors.pop()
                    axs[i].plot(x2, mean, c, label = 'estimated profit', alpha = 0.5)

                    axs[i].fill_between(
                            np.array(x2).ravel(),
                            mean - 1.96 * std,
                            mean + 1.96 * std,
                            alpha = 0.1,
                            label = r"95% confidence interval",
                            color = c
                    )
                    axs[i].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                                  ncol = 2, mode = "expand", borderaxespad = 0.)

                    axs[i].set_title('Profit curve - Campaign ' + str(i + 1), y = 1.0, pad = 43)

                plt.savefig(f'{self.simulation_name + self.learners[id].bandit_name + "ProfitPlots"}.pdf')
                plt.show()

        self.__plot_results(sns_style = 'matplotlib')  # uses default matplotlib style

    # TODO A PLOT HANDLER SHOULD DO ALL THE WORK HERE !
    # TODO -> PLOT CONFIDENCE INTERVALS !

    def __plot_results(self, remove_splines = True, offset_axes = True, opacity = 0.5, sns_context = 'notebook',
                       set_ticks = False, sns_style = 'matplotlib', enable_grid = True, hspace = 1, wspace = 0.5):

        clairvoyant_rewards_per_experiment_t1 = np.array(self.clairvoyant_rewards_per_experiment_t1)

        clairvoyant_rewards_per_experiment_t2 = np.array(self.clairvoyant_rewards_per_experiment_t2)
        learners_rewards_per_experiment = np.array(self.learners_rewards_per_experiment)

        if self.save_results_to_file:
            results = {}

            if self.clairvoyant_type != 'both':
                key = 'clairvoyant' + self.clairvoyant_type.capitalize()
                results[key] = {}
            else:
                results['clairvoyantAggregated'] = {}
                results['clairvoyantDisaggregated'] = {}

            for learner in self.learners:
                results[learner.bandit_name] = {}

        avgTotalProfit = 'avgTotalProfit'
        avgTotalProfitStd = 'avgTotalProfitStd'
        avgProfitPerDay = 'avgProfitPerDay'
        avgProfitPerDayStd = 'avgProfitPerDayStd '
        avgTotalRegret = 'avgTotalRegret'
        avgTotalRegretStd = 'avgTotalRegretStd'
        avgRegretPerDay = 'avgRegretPerDay'
        avgRegretPerDayStd = 'avgRegretPerDayStd'

        varsDict = {}

        varsDict[util.retrieve_name(avgTotalProfit)] = 0.0
        varsDict[util.retrieve_name(avgTotalProfitStd)] = 0.0
        varsDict[util.retrieve_name(avgProfitPerDay)] = 0.0
        varsDict[util.retrieve_name(avgProfitPerDayStd)] = 0.0
        varsDict[util.retrieve_name(avgTotalRegret)] = 0.0
        varsDict[util.retrieve_name(avgTotalRegretStd)] = 0.0
        varsDict[util.retrieve_name(avgRegretPerDay)] = 0.0
        varsDict[util.retrieve_name(avgRegretPerDayStd)] = 0.0

        if self.clairvoyant_type != 'both':
            varsDict[util.retrieve_name(avgTotalProfit)] = float(
                    np.mean(np.sum(clairvoyant_rewards_per_experiment_t1, axis = 1)))

            varsDict[util.retrieve_name(avgTotalProfitStd)] = float(
                    np.std(np.sum(clairvoyant_rewards_per_experiment_t1, axis = 1)))

            varsDict[util.retrieve_name(avgProfitPerDay)] = float(np.mean(clairvoyant_rewards_per_experiment_t1))
            varsDict[util.retrieve_name(avgProfitPerDayStd)] = float(np.std(clairvoyant_rewards_per_experiment_t1))

            if self.save_results_to_file:
                key = 'clairvoyant' + self.clairvoyant_type.capitalize()
                for v in varsDict:
                    results[key][v] = varsDict[v]

            print(f"\n***** FINAL RESULT CLAIRVOYANT ALGORITHM {self.clairvoyant_type.upper()} *****")
            print(f"days simulated: {self.days}")
            print(f"average clairvoyant total profit:\t {varsDict[util.retrieve_name(avgTotalProfit)]:.4f}€")
            print(
                    f"average clairvoyant total profit standard deviation:\t {varsDict[util.retrieve_name(avgTotalProfitStd)]:.4f}€")
            print("----------------------------")
            print(f"average clairvoyant profit per day:\t {varsDict[util.retrieve_name(avgProfitPerDay)]:.4f}€")
            print(
                    f"average clairvoyant profit per day standard deviation:\t {varsDict[util.retrieve_name(avgProfitPerDayStd)]:.4f}€")

        else:

            varsDict[util.retrieve_name(avgTotalProfit)] = float(
                    np.mean(np.sum(clairvoyant_rewards_per_experiment_t2, axis = 1)))
            varsDict[util.retrieve_name(avgTotalProfitStd)] = float(
                    np.std(np.sum(clairvoyant_rewards_per_experiment_t2, axis = 1)))
            varsDict[util.retrieve_name(avgProfitPerDay)] = float(np.mean(clairvoyant_rewards_per_experiment_t2))
            varsDict[util.retrieve_name(avgProfitPerDayStd)] = float(np.std(clairvoyant_rewards_per_experiment_t2))

            if self.save_results_to_file:
                key = 'clairvoyantDisaggregated'
                for v in varsDict:
                    results[key][v] = varsDict[v]

            print(f"\n***** FINAL RESULT CLAIRVOYANT ALGORITHM DISAGGREGATED *****")
            print(f"days simulated: {self.days}")
            print(f"average clairvoyant total profit:\t {varsDict[util.retrieve_name(avgTotalProfit)]:.4f}€")
            print(
                    f"average clairvoyant total profit standard deviation:\t {varsDict[util.retrieve_name(avgTotalProfitStd)]:.4f}€")
            print("----------------------------")
            print(f"average clairvoyant profit per day:\t {varsDict[util.retrieve_name(avgProfitPerDay)]:.4f}€")
            print(f"average standard deviation:\t {varsDict[util.retrieve_name(avgProfitPerDayStd)]:.4f}€")

            varsDict[util.retrieve_name(avgTotalProfit)] = float(
                    np.mean(np.sum(clairvoyant_rewards_per_experiment_t1, axis = 1)))
            varsDict[util.retrieve_name(avgTotalProfitStd)] = float(
                    np.std(np.sum(clairvoyant_rewards_per_experiment_t1, axis = 1)))
            varsDict[util.retrieve_name(avgProfitPerDay)] = float(np.mean(clairvoyant_rewards_per_experiment_t1))
            varsDict[util.retrieve_name(avgProfitPerDayStd)] = float(np.std(clairvoyant_rewards_per_experiment_t1))

            if self.save_results_to_file:
                key = 'clairvoyantAggregated'
                for v in varsDict:
                    results[key][v] = varsDict[v]

            print(f"\n***** FINAL RESULT CLAIRVOYANT ALGORITHM AGGREGATED *****")
            print(f"days simulated: {self.days}")
            print(
                    f"average clairvoyant total profit:\t {varsDict[util.retrieve_name(avgTotalProfit)]:.4f}€")
            print(
                    f"average clairvoyant total profit standard deviation:\t {varsDict[util.retrieve_name(avgTotalProfitStd)]:.4f}€")
            print("----------------------------")
            print(f"average clairvoyant profit per day:\t {varsDict[util.retrieve_name(avgProfitPerDay)] :.4f}€")
            print(f"average standard deviation:\t {varsDict[util.retrieve_name(avgProfitPerDayStd)]:.4f}€")

        for learnerIdx, learner in enumerate(self.learners):

            varsDict[util.retrieve_name(avgTotalProfit)] = float(
                    np.mean(np.sum(learners_rewards_per_experiment[learnerIdx], axis = 1)))

            varsDict[util.retrieve_name(avgTotalProfitStd)] = float(
                    np.std(np.sum(learners_rewards_per_experiment[learnerIdx], axis = 1)))

            varsDict[util.retrieve_name(avgProfitPerDay)] = float(np.mean(learners_rewards_per_experiment[learnerIdx]))

            varsDict[util.retrieve_name(avgProfitPerDayStd)] = float(
                    np.std(learners_rewards_per_experiment[learnerIdx]))

            varsDict[util.retrieve_name(avgTotalRegret)] = float(np.mean(
                    np.sum(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                           axis = 1)))

            varsDict[util.retrieve_name(avgTotalRegretStd)] = float(np.std(
                    np.sum(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                           axis = 1)))

            varsDict[util.retrieve_name(avgRegretPerDay)] = float(
                    np.mean(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx]))

            varsDict[util.retrieve_name(avgRegretPerDayStd)] = float(
                    np.std(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx]))

            if self.save_results_to_file:
                key = learner.bandit_name
                for v in varsDict:
                    results[key][v] = varsDict[v]

            print(f"\n***** FINAL RESULT LEARNER {learner.bandit_name} *****")

            print(
                    f"average total profit:\t {varsDict[util.retrieve_name(avgTotalProfit)]:.4f}€")
            print(
                    f"average total profit standard deviation:\t {varsDict[util.retrieve_name(avgTotalProfitStd)]:.4f}€")

            print("----------------------------")
            print(f"average profit per day :\t {varsDict[util.retrieve_name(avgProfitPerDay)]:.4f}€")
            print(
                    f"average profit per day standard deviation:\t {varsDict[util.retrieve_name(avgProfitPerDayStd)]:.4f}€")

            print("----------------------------")
            print(
                    f"average total regret\t {varsDict[util.retrieve_name(avgTotalRegret)]:.4f}€")
            print(
                    f"average total regret standard deviation:\t {varsDict[util.retrieve_name(avgTotalRegretStd)]:.4f}€")
            print()

            print("----------------------------")
            print(
                    f"average regret per day\t {varsDict[util.retrieve_name(avgRegretPerDay)]:.4f}€")
            print(
                    f"average regret per day standard deviation:\t {varsDict[util.retrieve_name(avgRegretPerDayStd)]:.4f}€")
            print()

        plt.close('all')

        sns.set_context(context = sns_context)
        if sns_style != 'matplotlib':
            sns.set_style(style = sns_style)

        if set_ticks:
            sns.set_style("ticks")

        d = np.linspace(0, self.days, self.days)

        colors = util.get_colors()

        colors_learners = [colors.pop() for _ in range(len(self.learners))]

        if len(self.learners) > 0:
            img, axss = plt.subplots(nrows = 2, ncols = 2, figsize = self.figsize)
            plt.subplots_adjust(hspace = hspace, top = 0.8, wspace = wspace)
        else:
            img, axss = plt.subplots(nrows = 1, ncols = 2, figsize = self.figsize)

        axs = axss.flatten()

        axs[0].set_xlabel("days")
        axs[0].set_ylabel("reward")

        if self.clairvoyant_type != 'both':
            axs[0].plot(d, np.mean(clairvoyant_rewards_per_experiment_t1, axis = 0), colors[-1],
                        label = "clairvoyant " + self.clairvoyant_type, alpha = opacity)

        else:
            axs[0].plot(d, np.mean(clairvoyant_rewards_per_experiment_t1, axis = 0), colors[-1],
                        label = "clairvoyant aggregated", alpha = opacity)
            axs[0].plot(d, np.mean(clairvoyant_rewards_per_experiment_t2, axis = 0), colors[-2],
                        label = "clairvoyant disaggregated", alpha = opacity)

        axs[1].set_xlabel("days")
        axs[1].set_ylabel("cumulative reward")

        for learnerIdx in range(len(self.learners)):
            bandit_name = self.learners[learnerIdx].bandit_name
            axs[0].plot(d, np.mean(learners_rewards_per_experiment[learnerIdx], axis = 0), colors_learners[learnerIdx],
                        label = bandit_name, alpha = opacity)

            mean = np.mean(learners_rewards_per_experiment[learnerIdx], axis = 0)
            std = np.std(learners_rewards_per_experiment[learnerIdx],
                         axis = 0)

            if self.plot_confidence_intervals:
                axs[0].fill_between(
                        np.array(d).ravel(),
                        mean - 1.96 * std,
                        mean + 1.96 * std,
                        alpha = 0.1,
                        label = r"95% confidence interval",
                        color = colors_learners[learnerIdx]
                )

        if self.clairvoyant_type != 'both':
            axs[1].plot(d, np.cumsum(np.mean(clairvoyant_rewards_per_experiment_t1, axis = 0)), colors[-1],
                        label = "clairvoyant " + self.clairvoyant_type, alpha = opacity)

        else:
            axs[1].plot(d, np.cumsum(np.mean(clairvoyant_rewards_per_experiment_t1, axis = 0)), colors[-1],
                        label = "clairvoyant aggregated", alpha = opacity)
            axs[1].plot(d, np.cumsum(np.mean(clairvoyant_rewards_per_experiment_t2, axis = 0)), colors[-2],
                        label = "clairvoyant disaggegated", alpha = opacity)

        for learnerIdx in range(len(self.learners)):
            bandit_name = self.learners[learnerIdx].bandit_name
            axs[1].plot(d, np.cumsum(np.mean(learners_rewards_per_experiment[learnerIdx], axis = 0)),
                        colors_learners[learnerIdx], label = bandit_name, alpha = opacity)

            std = np.std(
                    np.cumsum(learners_rewards_per_experiment[learnerIdx],
                              axis = 1), axis = 0)

            mean = np.cumsum(
                    np.mean(learners_rewards_per_experiment[learnerIdx],
                            axis = 0))

            if self.plot_confidence_intervals:
                axs[1].fill_between(
                        np.array(d).ravel(),
                        mean - 1.96 * std,
                        mean + 1.96 * std,
                        alpha = 0.1,
                        label = r"95% confidence interval",
                        color = colors_learners[learnerIdx]
                )

        axs[0].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                      ncol = 2, mode = "expand", borderaxespad = 0.)
        axs[1].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                      ncol = 2, mode = "expand", borderaxespad = 0.)

        if len(self.learners) > 0:
            axs[3].set_xlabel("days")
            axs[3].set_ylabel("cumulative regret")

            axs[2].set_xlabel("days")
            axs[2].set_ylabel("regret")

            for learnerIdx in range(len(self.learners)):
                bandit_name = self.learners[learnerIdx].bandit_name
                axs[3].plot(d, np.cumsum(
                        np.mean(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                                axis = 0)),
                            colors_learners[learnerIdx], label = bandit_name, alpha = opacity)

                std = np.std(
                        np.cumsum(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                                  axis = 1), axis = 0)

                mean = np.cumsum(
                        np.mean(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                                axis = 0))

                if self.plot_confidence_intervals:
                    axs[3].fill_between(
                            np.array(d).ravel(),
                            mean - 1.96 * std,
                            mean + 1.96 * std,
                            alpha = 0.1,
                            label = r"95% confidence interval",
                            color = colors_learners[learnerIdx]
                    )

            for learnerIdx in range(len(self.learners)):
                bandit_name = self.learners[learnerIdx].bandit_name
                axs[2].plot(d,
                            np.mean(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                                    axis = 0), colors_learners[learnerIdx], label = bandit_name, alpha = opacity)

                mean = np.mean(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                               axis = 0)
                std = np.std(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                             axis = 0)

                if self.plot_confidence_intervals:
                    axs[2].fill_between(
                            np.array(d).ravel(),
                            mean - 1.96 * std,
                            mean + 1.96 * std,
                            alpha = 0.1,
                            label = r"95% confidence interval",
                            color = colors_learners[learnerIdx]
                    )

            """if self.find_learner_idx(util.BanditNames.GPTS_Learner.name) >= 0:
                regret_upper_bound = []
                for i in range(self.days + 1):
                    regret_upper_bound.append(util.regret_upper_bound_gp_ts(t = i,
                                                                            arms = self.n_arms,
                                                                            sets = self.campaigns,
                                                                            input_dimension = 1, K = 40))

                axs[3].plot(regret_upper_bound, colors[0], alpha = opacity, label = "GP-TS Regret Bound")

            idx = self.find_learner_idx(util.BanditNames.GTS_Learner.name)
            if idx > -1:
                delta = util.compute_delta(self.learners[idx].arms,
                                           self.learner_profit_functions_per_experiment[0],
                                           self.buds,
                                           self.avg_clairvoyant_profit_functions_t1,
                                           self.campaigns)

                regret_upper_bound = util.regret_upper_bound_gts(t = self.days,
                                                                 arms = self.n_arms,
                                                                 sets = self.campaigns,
                                                                 delta_min = delta, K = 30)
                axs[3].axhline(regret_upper_bound, color = colors[0], alpha = opacity, label = "GTS Regret Bound")
"""
            axs[3].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                          ncol = 2, mode = "expand", borderaxespad = 0.)
            axs[2].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                          ncol = 2, mode = "expand", borderaxespad = 0.)

        if remove_splines:
            if offset_axes:
                for ax in axs:
                    sns.despine(ax = ax, offset = 5, trim = False)
            else:
                sns.despine()

        if enable_grid:
            for ax in axs:
                ax.grid(alpha = 0.2)

        # REALLY BAD CODE HERE !!!!!!

        if len(self.learners) > 2:
            pad = 79
        elif len(self.learners) > 1:
            pad = 58
        elif len(self.learners) > 0:
            pad = 43
        else:
            pad = 36

        axs[0].set_title('Reward', y = 1.0, pad = pad)
        axs[1].set_title('Cumulative Reward', y = 1.0, pad = pad)

        if len(self.learners) > 0:
            if len(self.learners) > 2:
                pad = 65
            elif len(self.learners) > 1:
                pad = 45
            elif len(self.learners) > 0:
                pad = 28

            axs[3].set_title('Cumulative Regret', y = 1.0, pad = pad)
            axs[2].set_title('Regret', y = 1.0, pad = pad)

        mng = plt.get_current_fig_manager()
        mng.resize(*mng.window.maxsize())

        plt.savefig(f'{self.simulation_name + "PerformancePlot"}.pdf')
        plt.show()

        if not self.plot_confidence_intervals:

            for learnerIdx, learner in enumerate(self.learners):
                plt.close('all')
                sns.set_context(context = sns_context)
                if sns_style != 'matplotlib':
                    sns.set_style(style = sns_style)

                if set_ticks:
                    sns.set_style("ticks")

                d = np.linspace(0, self.days, self.days)

                colors = util.get_colors()

                colors_learners = [colors.pop() for _ in range(len(self.learners))]

                if len(self.learners) > 0:
                    img, axss = plt.subplots(nrows = 2, ncols = 2, figsize = self.figsize)
                    plt.subplots_adjust(hspace = hspace, top = 0.8, wspace = wspace)
                else:
                    img, axss = plt.subplots(nrows = 1, ncols = 2, figsize = self.figsize)

                axs = axss.flatten()

                axs[0].set_xlabel("days")
                axs[0].set_ylabel("reward")

                if self.clairvoyant_type != 'both':
                    axs[0].plot(d, np.mean(clairvoyant_rewards_per_experiment_t1, axis = 0), colors[-1],
                                label = "clairvoyant " + self.clairvoyant_type , alpha = opacity)

                else:
                    axs[0].plot(d, np.mean(clairvoyant_rewards_per_experiment_t1, axis = 0), colors[-1],
                                label = "clairvoyant aggregated", alpha = opacity)
                    axs[0].plot(d, np.mean(clairvoyant_rewards_per_experiment_t2, axis = 0), colors[-2],
                                label = "clairvoyant disaggregated", alpha = opacity)

                axs[1].set_xlabel("days")
                axs[1].set_ylabel("cumulative reward")

                bandit_name = self.learners[learnerIdx].bandit_name
                axs[0].plot(d, np.mean(learners_rewards_per_experiment[learnerIdx], axis = 0),
                            colors_learners[learnerIdx],
                            label = bandit_name, alpha = opacity)

                mean = np.mean(learners_rewards_per_experiment[learnerIdx], axis = 0)
                std = np.std(learners_rewards_per_experiment[learnerIdx],
                             axis = 0)

                axs[0].fill_between(
                        np.array(d).ravel(),
                        mean - 1.96 * std,
                        mean + 1.96 * std,
                        alpha = 0.1,
                        label = r"95% confidence interval",
                        color = colors_learners[learnerIdx]
                )

                if self.clairvoyant_type != 'both':
                    axs[1].plot(d, np.cumsum(np.mean(clairvoyant_rewards_per_experiment_t1, axis = 0)), colors[-1],
                                label = "clairvoyant " + self.clairvoyant_type, alpha = opacity)

                else:
                    axs[1].plot(d, np.cumsum(np.mean(clairvoyant_rewards_per_experiment_t1, axis = 0)), colors[-1],
                                label = "clairvoyant aggregated", alpha = opacity)
                    axs[1].plot(d, np.cumsum(np.mean(clairvoyant_rewards_per_experiment_t2, axis = 0)), colors[-2],
                                label = "clairvoyant disaggegated", alpha = opacity)

                bandit_name = self.learners[learnerIdx].bandit_name
                axs[1].plot(d, np.cumsum(np.mean(learners_rewards_per_experiment[learnerIdx], axis = 0)),
                            colors_learners[learnerIdx], label = bandit_name, alpha = opacity)

                std = np.std(
                        np.cumsum(learners_rewards_per_experiment[learnerIdx],
                                  axis = 1), axis = 0)

                mean = np.cumsum(
                        np.mean(learners_rewards_per_experiment[learnerIdx],
                                axis = 0))

                axs[1].fill_between(
                        np.array(d).ravel(),
                        mean - 1.96 * std,
                        mean + 1.96 * std,
                        alpha = 0.1,
                        label = r"95% confidence interval",
                        color = colors_learners[learnerIdx]
                )

                axs[0].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                              ncol = 2, mode = "expand", borderaxespad = 0.)
                axs[1].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                              ncol = 2, mode = "expand", borderaxespad = 0.)

                if len(self.learners) > 0:
                    axs[3].set_xlabel("days")
                    axs[3].set_ylabel("cumulative regret")

                    axs[2].set_xlabel("days")
                    axs[2].set_ylabel("regret")

                    bandit_name = self.learners[learnerIdx].bandit_name
                    axs[3].plot(d, np.cumsum(
                            np.mean(
                                    clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                                    axis = 0)),
                                colors_learners[learnerIdx], label = bandit_name, alpha = opacity)

                    std = np.std(
                            np.cumsum(
                                    clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                                    axis = 1), axis = 0)

                    mean = np.cumsum(
                            np.mean(
                                    clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                                    axis = 0))

                    axs[3].fill_between(
                            np.array(d).ravel(),
                            mean - 1.96 * std,
                            mean + 1.96 * std,
                            alpha = 0.1,
                            label = r"95% confidence interval",
                            color = colors_learners[learnerIdx]
                    )

                    bandit_name = self.learners[learnerIdx].bandit_name
                    axs[2].plot(d,
                                np.mean(clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[
                                    learnerIdx],
                                        axis = 0), colors_learners[learnerIdx], label = bandit_name,
                                alpha = opacity)

                    mean = np.mean(
                            clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                            axis = 0)
                    std = np.std(
                            clairvoyant_rewards_per_experiment_t1 - learners_rewards_per_experiment[learnerIdx],
                            axis = 0)

                    axs[2].fill_between(
                            np.array(d).ravel(),
                            mean - 1.96 * std,
                            mean + 1.96 * std,
                            alpha = 0.1,
                            label = r"95% confidence interval",
                            color = colors_learners[learnerIdx]
                    )

                    axs[3].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                                  ncol = 2, mode = "expand", borderaxespad = 0.)
                    axs[2].legend(bbox_to_anchor = (0., 1.02, 1., .102), loc = 3,
                                  ncol = 2, mode = "expand", borderaxespad = 0.)

                if remove_splines:
                    if offset_axes:
                        for ax in axs:
                            sns.despine(ax = ax, offset = 5, trim = False)
                    else:
                        sns.despine()

                if enable_grid:
                    for ax in axs:
                        ax.grid(alpha = 0.2)

                # REALLY BAD CODE HERE !!!!!!

                pad = 43

                axs[0].set_title('Reward', y = 1.0, pad = pad)
                axs[1].set_title('Cumulative Reward', y = 1.0, pad = pad)

                pad = 28
                axs[3].set_title('Cumulative Regret', y = 1.0, pad = pad)
                axs[2].set_title('Regret', y = 1.0, pad = pad)

                mng = plt.get_current_fig_manager()
                mng.resize(*mng.window.maxsize())

                plt.savefig(f'{self.simulation_name + learner.bandit_name + "PerformancePlot"}.pdf')
                plt.show()

        if self.save_results_to_file:
            with open(f'{self.simulation_name}.json', 'w') as f:
                json.dump(results, f, ensure_ascii = False, indent = 4)

        f.close()
