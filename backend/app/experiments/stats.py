from scipy.stats import ttest_ind


def welch_test(scores_a: list[float], scores_b: list[float]) -> dict:
    if len(scores_a) < 2 or len(scores_b) < 2:
        return {
            "n_a": len(scores_a), "n_b": len(scores_b),
            "mean_a": None, "mean_b": None,
            "effect_size": None, "t_stat": None,
            "p_value": None, "significant": False,
        }

    t_stat, p_value = ttest_ind(scores_a, scores_b, equal_var=False)
    mean_a = sum(scores_a) / len(scores_a)
    mean_b = sum(scores_b) / len(scores_b)
    return {
        "n_a": len(scores_a),
        "n_b": len(scores_b),
        "mean_a": round(mean_a, 2),
        "mean_b": round(mean_b, 2),
        "effect_size": round(float(mean_b - mean_a), 3),
        "t_stat": round(float(t_stat), 4),
        "p_value": round(float(p_value), 6),
        "significant": bool(p_value < 0.05),
    }
