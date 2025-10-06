import json
import random

def load_data(filepath):
    """Loads data from a JSON file."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"Warning: Data file not found at {filepath}. Returning empty list/dict.")
        return []
    except json.JSONDecodeError:
        print(f"Warning: Could not decode JSON from {filepath}. Returning empty list/dict.")
        return []

def evaluate_formula(formula, **kwargs):
    """
    Evaluates a mathematical formula string with given variables.
    Example: evaluate_formula("100 * (1.1 ** (level - 1))", level=5)
    """
    try:
        return eval(formula, {"__builtins__": None}, kwargs)
    except Exception as e:
        print(f"Error evaluating formula '{formula}': {e}")
        return 0

def weighted_choice(choices_dict):
    """
    Makes a weighted random choice from a dictionary of {choice: weight}.
    """
    total_weight = sum(choices_dict.values())
    if total_weight == 0:
        return None

    rand_val = random.uniform(0, total_weight)
    cumulative_weight = 0

    for choice, weight in choices_dict.items():
        cumulative_weight += weight
        if rand_val <= cumulative_weight:
            return choice
    return None # Fallback