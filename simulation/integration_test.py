import pandas as pd
from cadCAD.configuration import Experiment
from cadCAD.configuration.utils import config_sim
from cadCAD.engine import ExecutionContext, ExecutionMode, Executor
from cadCAD import configs

import unittest
import numpy as np
import copy

from utils import (new_probability_func, new_exponential_func, new_gamma_func,
                   new_random_number_func, new_choice_func)
from hatch import create_token_batches, Commons
from network_utils import (bootstrap_network, get_participants,
                           get_edges_by_type)
from simulation import (bootstrap_simulation, CommonsSimulationConfiguration,
                        partial_state_update_blocks)


def run_simulation(c: CommonsSimulationConfiguration):
    initial_conditions, simulation_parameters = bootstrap_simulation(c)

    exp = Experiment()
    exp.append_configs(
        initial_state=initial_conditions,
        partial_state_update_blocks=partial_state_update_blocks,
        sim_configs=simulation_parameters
    )

    # Do not use multi_proc, breaks ipdb.set_trace()
    exec_mode = ExecutionMode()
    single_proc_context = ExecutionContext(exec_mode.local_mode)
    executor = Executor(single_proc_context, configs)

    raw_system_events, tensor_field, sessions = executor.execute()

    df = pd.DataFrame(raw_system_events)
    df_final = df

    result = {
        "timestep": list(df_final["timestep"]),
        "funding_pool": list(df_final["funding_pool"]),
        "token_price": list(df_final["token_price"]),
        "sentiment": list(df_final["sentiment"])
    }
    return result, df_final


class TestParticipant(unittest.TestCase):
    def setUp(self):
        c = CommonsSimulationConfiguration(random_seed=1)
        results, df_final = run_simulation(c)
        self.df_final = df_final
        PSUBs_labels = {}
        for idx, block in enumerate(partial_state_update_blocks):
            PSUBs_labels[idx+1] = block["label"]

        self.PSUBs_labels = PSUBs_labels

    def test_participant_token_batch_age_is_updated_every_timestep(self):
            """
            Test that the age of the Participants' token batch is updated every
            timestep. The test checks if the older token batch age has the same
            age
            of the simulation (timestep). It considers that at least one
            participant stays in the commons from the beginning to the end of the
            simulation.
            """
            for index, row in self.df_final.iterrows():
                timestep = row["timestep"]
                network = row["network"]
                participants = get_participants(network)

            participants_token_batch_ages = []
            for i, participant in participants:
                participants_token_batch_ages.append(participant.holdings.age_days)
            # Check if the older token batch has the same age of the simulation
            self.assertEqual(max(participants_token_batch_ages), timestep)

    def test_conviction_is_updated_once_by_timestep(self):
        for index, row in self.df_final.iterrows():
            timestep = row["timestep"]
            substep = row["substep"]
            network = row["network"]
            # Arbitrarily testing timestep 2
            if timestep == 2:
                print("substep", substep)
                support_edges = get_edges_by_type(network, "support")
                conviction_list = []
                for i, j in support_edges:
                    edge = network.edges[i, j]
                    prior_conviction = edge["conviction"]
                    conviction_list.append(prior_conviction)
                # If there is no timestep before, there is no need (later test
                # this with the last substep of the last timestep)
                if substep > 1:
                    if self.PSUBs_labels[substep] == "Generate new proposals":
                        length_diff = len(conviction_list) - len(prior_conviction_list)
                        priot_conviction_list = prior_conviction_list + [0.0] * length_diff
                        self.assertEqual(conviction_list, priot_conviction_list)
                        prior_conviction_list = copy.deepcopy(conviction_list)

                    if self.PSUBs_labels[substep] == "Calculate proposals' conviction":
                        # Checks that no proposal have been added or removed
                        self.assertEqual(len(conviction_list), len(prior_conviction_list))
                        self.assertFalse(conviction_list == prior_conviction_list)

                    else:
                        self.assertEqual(conviction_list, prior_conviction_list)

                    prior_conviction_list = copy.deepcopy(conviction_list)
                prior_conviction_list = copy.deepcopy(conviction_list)
