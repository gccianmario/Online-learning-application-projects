from random import randint
import numpy as np
from Graph import Graph


def get_probabilities(quantity, padding=0.5):
    """it return a random list of probabilities that sum to 1-padding"""

    if int(quantity) <= 0:
        raise Exception("quantity Value Error")
    if float(padding) < 0 or float(padding) >= 1:
        raise Exception("padding Value Error")

    probabilities = []
    random_samples = np.array([0] * quantity)

    for i in range(quantity):
        random_samples[i] = float(randint(1, 100))

    normalizer = (1 - padding) / np.sum(random_samples)

    for i in range(quantity):
        probabilities.append(random_samples[i] * normalizer)

    # add numerical noise to first element to try to ensure sum to 1-padding
    probabilities[0] = probabilities[0] + ((1 - padding) - np.sum(probabilities))

    return probabilities


def random_fully_connected_graph(products=[], padding=0.1):
    """ Generate a fully connected random graph with the given Products
        the weights will sum to 1-padding """
    graph = Graph()

    for prod in products:
        graph.add_node(prod)

    for prod in products:
        weights = get_probabilities(4, padding=padding)  # to change weights change here
        child_products = products.copy()
        child_products.remove(prod)

        for i, prod_child in enumerate(child_products):
            graph.add_edge(prod, prod_child, weights[i])

    return graph


def new_alpha_function(saturation_speed=1, max_value=1, activation=0.1):
    """ When using the alpha functions remember to clip them to 0 """
    return lambda x: (-1 + 2 / (1 + np.exp(- saturation_speed * (x - activation)))) * max_value