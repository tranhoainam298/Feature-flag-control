"""Generate bucketing distribution and independence report for FlagOps.

Simulates 100,000 evaluations across multiple scenarios:
1. Uniformity test (50/50 and multi-variate distribution).
2. Monotonic rollout progression (10% -> 20% -> 50%).
3. Inter-flag independence verification (ensuring ~1% overlap for two 10% flags).

Saves publication-quality chart to docs/diagrams/bucketing-distribution.png.
"""

import os
import sys
import uuid
from collections import Counter

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import matplotlib.pyplot as plt

from app.engine.bucketing import bucket


def generate_report() -> None:
    if os.path.exists("/docs"):
        output_dir = "/docs/diagrams"
    else:
        output_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../docs/diagrams"))
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "bucketing-distribution.png")

    num_samples = 100000
    print(f"Generating bucketing report with {num_samples:,} samples...")

    # Pre-generate user IDs
    users = [str(uuid.UUID(int=i + 1)) for i in range(num_samples)]

    # -------------------------------------------------------------------------
    # Scenario 1: 50 / 50 Uniformity
    # -------------------------------------------------------------------------
    dist_50_50 = [
        {"variation_id": "Control (A)", "weight": 50.0},
        {"variation_id": "Treatment (B)", "weight": 50.0},
    ]
    results_50_50 = [bucket(uid, "checkout-redesign", "rule-1", dist_50_50) for uid in users]
    counts_50 = Counter(results_50_50)
    pct_a = counts_50["Control (A)"] / num_samples * 100
    pct_b = counts_50["Treatment (B)"] / num_samples * 100

    # -------------------------------------------------------------------------
    # Scenario 2: 4-way Split (10% / 20% / 30% / 40%)
    # -------------------------------------------------------------------------
    dist_multi = [
        {"variation_id": "Var 1 (10%)", "weight": 10.0},
        {"variation_id": "Var 2 (20%)", "weight": 20.0},
        {"variation_id": "Var 3 (30%)", "weight": 30.0},
        {"variation_id": "Var 4 (40%)", "weight": 40.0},
    ]
    results_multi = [bucket(uid, "pricing-test", "rule-1", dist_multi) for uid in users]
    counts_multi = Counter(results_multi)
    pct_multi = [counts_multi[entry["variation_id"]] / num_samples * 100 for entry in dist_multi]

    # -------------------------------------------------------------------------
    # Scenario 3: Monotonic Rollout (10% -> 20% -> 50%)
    # -------------------------------------------------------------------------
    dist_10 = [{"variation_id": "on", "weight": 10.0}, {"variation_id": "off", "weight": 90.0}]
    dist_20 = [{"variation_id": "on", "weight": 20.0}, {"variation_id": "off", "weight": 80.0}]
    dist_50 = [{"variation_id": "on", "weight": 50.0}, {"variation_id": "off", "weight": 50.0}]

    users_10 = {uid for uid in users if bucket(uid, "new-ui", "rule-1", dist_10) == "on"}
    users_20 = {uid for uid in users if bucket(uid, "new-ui", "rule-1", dist_20) == "on"}
    users_50 = {uid for uid in users if bucket(uid, "new-ui", "rule-1", dist_50) == "on"}

    is_monotonic = users_10.issubset(users_20) and users_20.issubset(users_50)
    print(f"Monotonic property verified (10% subset 20% subset 50%): {is_monotonic}")

    # -------------------------------------------------------------------------
    # Scenario 4: Flag Independence (Flag Alpha 10% vs Flag Beta 10%)
    # -------------------------------------------------------------------------
    alpha_on = {uid for uid in users if bucket(uid, "flag-alpha", "rule-1", dist_10) == "on"}
    beta_on = {uid for uid in users if bucket(uid, "flag-beta", "rule-1", dist_10) == "on"}
    overlap = alpha_on.intersection(beta_on)
    overlap_pct = len(overlap) / num_samples * 100
    print(f"Flag overlap (Alpha 10% & Beta 10%): {overlap_pct:.2f}% (Theoretical: 1.00%)")

    # -------------------------------------------------------------------------
    # Render Matplotlib Figure
    # -------------------------------------------------------------------------
    fig, axs = plt.subplots(2, 2, figsize=(13, 9))
    plt.subplots_adjust(hspace=0.35, wspace=0.25)
    fig.suptitle("FlagOps — MurmurHash3 Sticky Bucketing Analysis", fontsize=16, fontweight="bold")

    # Chart 1: 50/50 Distribution
    axs[0, 0].bar(
        ["Control (50%)", "Treatment (50%)"],
        [pct_a, pct_b],
        color=["#2563eb", "#10b981"],
        width=0.45,
    )
    axs[0, 0].axhline(50.0, color="red", linestyle="--", alpha=0.7, label="Expected (50.0%)")
    axs[0, 0].set_ylim(45, 55)
    axs[0, 0].set_ylabel("Measured Percentage (%)")
    axs[0, 0].set_title(f"A/B 50/50 Uniformity (N={num_samples:,})")
    for i, v in enumerate([pct_a, pct_b]):
        axs[0, 0].text(i, v + 0.3, f"{v:.2f}%", ha="center", fontweight="semibold")
    axs[0, 0].legend(loc="upper right")

    # Chart 2: 4-Way Multi-variate Split
    labels_multi = ["Var 1\n(10%)", "Var 2\n(20%)", "Var 3\n(30%)", "Var 4\n(40%)"]
    expected_multi = [10.0, 20.0, 30.0, 40.0]
    axs[0, 1].bar(labels_multi, pct_multi, color="#6366f1", width=0.5, label="Measured")
    axs[0, 1].scatter(range(4), expected_multi, color="red", s=60, zorder=5, label="Target Weight")
    axs[0, 1].set_ylabel("Measured Percentage (%)")
    axs[0, 1].set_title("Multi-variate Distribution (10/20/30/40)")
    for i, v in enumerate(pct_multi):
        axs[0, 1].text(i, v + 0.8, f"{v:.2f}%", ha="center", fontsize=9, fontweight="semibold")
    axs[0, 1].legend(loc="upper left")

    # Chart 3: Monotonic Rollout Expansion
    rollout_stages = ["Stage 1\n(10% Rollout)", "Stage 2\n(20% Rollout)", "Stage 3\n(50% Rollout)"]
    user_counts = [len(users_10), len(users_20), len(users_50)]
    axs[1, 0].plot(
        rollout_stages,
        user_counts,
        marker="o",
        linewidth=2.5,
        color="#059669",
        markersize=8,
    )
    axs[1, 0].set_ylabel("Active User Count (Targeted)")
    axs[1, 0].set_title("Monotonic Rollout Continuity\n(100% Retained at Higher Rollout)")
    for i, count in enumerate(user_counts):
        axs[1, 0].text(
            i,
            count + 1500,
            f"{count:,}\n({count / num_samples * 100:.1f}%)",
            ha="center",
            fontweight="semibold",
        )
    axs[1, 0].set_ylim(0, 60000)

    # Chart 4: Inter-Flag Independence
    both_pct = overlap_pct
    alpha_only = (len(alpha_on) - len(overlap)) / num_samples * 100
    beta_only = (len(beta_on) - len(overlap)) / num_samples * 100
    neither_pct = 100.0 - (alpha_only + beta_only + both_pct)

    categories = [
        "Both Flags\n(~1% Exp)",
        "Alpha Only\n(~9% Exp)",
        "Beta Only\n(~9% Exp)",
        "Neither\n(~81% Exp)",
    ]
    indep_vals = [both_pct, alpha_only, beta_only, neither_pct]
    colors_indep = ["#f59e0b", "#3b82f6", "#8b5cf6", "#9ca3af"]

    axs[1, 1].bar(categories, indep_vals, color=colors_indep, width=0.55)
    axs[1, 1].set_ylabel("Population Share (%)")
    title_indep = f"Flag Independence (Hash Salt)\nBoth Active: {both_pct:.2f}% (Expected: 1.00%)"
    axs[1, 1].set_title(title_indep)

    for i, v in enumerate(indep_vals):
        axs[1, 1].text(i, v + 1.2, f"{v:.2f}%", ha="center", fontsize=9, fontweight="semibold")

    # Save to disk
    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()

    print(f"Chart saved successfully: {output_path}")


if __name__ == "__main__":
    generate_report()
