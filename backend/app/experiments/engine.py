from app.core.db import get_db
from app.experiments.splitter import assign_variant
from app.experiments.stats import welch_test


def create_experiment(
    team_id: str,
    name: str,
    variant_a: dict,
    variant_b: dict,
    hypothesis: str = "",
    traffic_split: float = 0.5,
    min_sample_size: int = 100,
    max_sample_size: int = 2000,
) -> dict:
    db = get_db()
    result = db.table("experiments").insert({
        "team_id": team_id,
        "name": name,
        "hypothesis": hypothesis,
        "variant_a": variant_a,
        "variant_b": variant_b,
        "traffic_split": traffic_split,
        "min_sample_size": min_sample_size,
        "max_sample_size": max_sample_size,
        "status": "running",
    }).execute()
    return result.data[0]


def apply_to_request(team_id: str, request_key: str) -> tuple[str, dict] | None:
    db = get_db()
    experiments = (
        db.table("experiments")
        .select("id, variant_a, variant_b, traffic_split")
        .eq("team_id", team_id)
        .eq("status", "running")
        .limit(1)
        .execute()
    ).data

    if not experiments:
        return None

    exp = experiments[0]
    variant = assign_variant(exp["id"], request_key, float(exp["traffic_split"]))
    config = exp["variant_a"] if variant == "a" else exp["variant_b"]
    return variant, {**config, "experiment_id": exp["id"]}


def recompute_stats(experiment_id: str) -> dict | None:
    db = get_db()

    exp = (
        db.table("experiments")
        .select("*")
        .eq("id", experiment_id)
        .single()
        .execute()
    ).data
    if not exp or exp["status"] != "running":
        return None

    assignments = (
        db.table("experiment_assignments")
        .select("request_id, variant")
        .eq("experiment_id", experiment_id)
        .execute()
    ).data or []

    a_ids = [r["request_id"] for r in assignments if r["variant"] == "a"]
    b_ids = [r["request_id"] for r in assignments if r["variant"] == "b"]

    def get_scores(request_ids: list[str]) -> list[float]:
        if not request_ids:
            return []
        response_ids = [
            r["id"]
            for r in (
                db.table("responses")
                .select("id, request_id")
                .in_("request_id", request_ids)
                .execute()
            ).data or []
        ]
        if not response_ids:
            return []
        return [
            float(r["quality_score"])
            for r in (
                db.table("eval_scores")
                .select("quality_score")
                .in_("response_id", response_ids)
                .execute()
            ).data or []
        ]

    scores_a = get_scores(a_ids)
    scores_b = get_scores(b_ids)
    stats = welch_test(scores_a, scores_b)

    n_total = len(a_ids) + len(b_ids)
    update: dict = {"sample_size": n_total}

    if stats["p_value"] is not None:
        update["p_value"] = stats["p_value"]
        update["effect_size"] = stats["effect_size"]

    # Auto-conclude
    if n_total >= exp["min_sample_size"] and (
        stats["significant"] or n_total >= exp["max_sample_size"]
    ):
        if stats["effect_size"] is not None:
            winner = "b" if stats["effect_size"] > 0 else "a"
            if not stats["significant"]:
                winner = "tie"
        else:
            winner = "tie"

        update["status"] = "concluded"
        update["winner"] = winner
        update["concluded_at"] = "now()"

        # Shift traffic toward winner (cap at 0.6)
        if winner == "b":
            update["traffic_split"] = min(0.6, float(exp["traffic_split"]) + 0.1)
        elif winner == "a":
            update["traffic_split"] = max(0.4, float(exp["traffic_split"]) - 0.1)

    db.table("experiments").update(update).eq("id", experiment_id).execute()
    return {**stats, **update}
