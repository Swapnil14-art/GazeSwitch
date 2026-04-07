import random
import statistics

from dwell_learner import DwellLearner

IDEAL_DWELL = 0.7
STEPS = 2000  # simulation length
WARMUP_STEPS = 500  # ignore early unstable phase
REGRET_WINDOW = 1.0  # seconds, from main app
SUCCESS_WINDOW = 2.0  # seconds, from main app
NOISE_FACTOR = 0.05  # randomness in user timing


def simulate_user_response(current_dwell, ideal_dwell):
    """
    Simulate a user response to an auto-focus event.

    Returns:
        result_type (str): "regret" or "success"
        strength (float): magnitude of feedback (0-1)
    """
    error = current_dwell - ideal_dwell

    # Add small random noise
    error += random.uniform(-NOISE_FACTOR, NOISE_FACTOR)

    if error < 0:
        # Too fast - user likely corrects (regret)
        # Simulate time_since_focus between 0 and REGRET_WINDOW
        time_since_focus = random.uniform(0, REGRET_WINDOW)
        strength = 1 - (time_since_focus / REGRET_WINDOW)
        return "regret", strength
    else:
        # Dwell long enough - success
        # Simulate user lingering 0 to SUCCESS_WINDOW extra
        time_since_focus = random.uniform(SUCCESS_WINDOW, SUCCESS_WINDOW * 2)
        strength = min(1.0, (time_since_focus - SUCCESS_WINDOW) / SUCCESS_WINDOW)
        return "success", strength


def run_simulation():
    learner = DwellLearner(base_dwell=0.3)

    history = []
    regrets = 0
    successes = 0
    converged_step = None

    for step in range(STEPS):
        current = learner.get()

        result_type, strength = simulate_user_response(current, IDEAL_DWELL)

        if result_type == "regret":
            learner.on_regret(strength)
            regrets += 1
        else:
            learner.on_success(strength)
            successes += 1

        new_dwell = learner.get()
        history.append(new_dwell)

        # Detect first convergence within 0.05 of ideal dwell
        if converged_step is None and abs(new_dwell - IDEAL_DWELL) < 0.05:
            converged_step = step

    return {
        "history": history,
        "regrets": regrets,
        "successes": successes,
        "converged_step": converged_step,
    }


def compute_metrics(result):
    history = result["history"][WARMUP_STEPS:]  # ignore warmup

    avg_error = sum(abs(h - IDEAL_DWELL) for h in history) / len(history)
    regret_rate = result["regrets"] / (result["regrets"] + result["successes"])
    stability_range = max(history) - min(history)
    variance = statistics.variance(history) if len(history) > 1 else 0
    bias = sum(history) / len(history) - IDEAL_DWELL

    return {
        "avg_error": avg_error,
        "regret_rate": regret_rate,
        "stability_range": stability_range,
        "variance": variance,
        "bias": bias,
        "converged_step": result["converged_step"],
        "final_dwell": history[-1],
    }


if __name__ == "__main__":
    result = run_simulation()
    metrics = compute_metrics(result)

    print("\n--- Simulation Results ---\n")
    print(f"Final dwell:        {metrics['final_dwell']:.3f}")
    print(f"Avg error:          {metrics['avg_error']:.3f}")
    print(f"Bias:               {metrics['bias']:.3f}")
    print(f"Regret rate:        {metrics['regret_rate']:.3f}")
    print(f"Stability (range):  {metrics['stability_range']:.3f}")
    print(f"Variance:           {metrics['variance']:.6f}")
    print(f"Converged at step:  {metrics['converged_step']}")
