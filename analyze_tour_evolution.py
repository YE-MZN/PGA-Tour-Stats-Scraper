import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


METRIC_COLUMNS = {
    "Driving Distance": ("metric__Total Distance", "metric__Total Drives"),
    "Driving Accuracy Percentage": ("metric__Fairways Hit", "metric__Possible Fairways"),
    "Greens in Regulation Percentage": ("metric__Greens Hit", "metric__# Holes"),
    "Birdie Average": ("metric__# of Birdies", "metric__Total Rounds"),
    "3-Putt Avoidance": ("metric__Total 3 Putts", "metric__Total Holes (overall)"),
}
SCORING_AVERAGE = "Scoring Average"
METRIC_LABELS = {
    "driving_distance_yards": ("Driving distance", "Yards", "#bd4d34"),
    "driving_accuracy_pct": ("Driving accuracy", "% of possible fairways", "#176c68"),
    "gir_pct": ("Greens in regulation", "% of holes", "#3478a8"),
    "birdies_per_round": ("Birdies", "Per round", "#d08b25"),
    "three_putts_per_100_holes": ("Three-putt frequency", "Per 100 holes", "#685b83"),
    "scoring_average": ("Scoring average", "Strokes per round", "#343b40"),
}


def numeric_values(series: pd.Series) -> pd.Series:
    return pd.to_numeric(
        series.astype("string").str.replace(",", "", regex=False),
        errors="coerce",
    ).astype("float64")


def summarize_year(path: Path) -> dict[str, int | float | str]:
    columns = {
        "event_date",
        "tournament",
        "player",
        "stat_name",
        "metric__Avg",
        "metric__Total Rounds",
    }
    columns.update(column for pair in METRIC_COLUMNS.values() for column in pair)
    data = pd.read_csv(path, usecols=lambda column: column in columns, low_memory=False)
    keys = ["event_date", "tournament", "player"]
    result: dict[str, int | float | str] = {
        "season": int(path.name.split("_")[-1].split(".")[0]),
        "data_through": str(data["event_date"].max()),
    }

    for stat, (numerator_column, denominator_column) in METRIC_COLUMNS.items():
        rows = data[data["stat_name"].eq(stat)].drop_duplicates(keys)
        numerator = numeric_values(rows[numerator_column])
        denominator = numeric_values(rows[denominator_column])
        valid = numerator.notna() & denominator.notna() & denominator.gt(0)
        value = numerator[valid].sum() / denominator[valid].sum()
        if stat in {"Driving Accuracy Percentage", "Greens in Regulation Percentage"}:
            value *= 100
        if stat == "3-Putt Avoidance":
            value *= 100
        column_name = {
            "Driving Distance": "driving_distance_yards",
            "Driving Accuracy Percentage": "driving_accuracy_pct",
            "Greens in Regulation Percentage": "gir_pct",
            "Birdie Average": "birdies_per_round",
            "3-Putt Avoidance": "three_putts_per_100_holes",
        }[stat]
        result[column_name] = value
        result[f"{column_name}_player_events"] = int(valid.sum())

    scoring = data[data["stat_name"].eq(SCORING_AVERAGE)].drop_duplicates(keys)
    rounds = numeric_values(scoring["metric__Total Rounds"])
    average = pd.to_numeric(scoring["metric__Avg"], errors="coerce").astype("float64")
    valid_scoring = average.notna() & rounds.notna() & rounds.gt(0)
    result["scoring_average"] = (average[valid_scoring] * rounds[valid_scoring]).sum() / rounds[
        valid_scoring
    ].sum()
    result["scoring_average_player_events"] = int(valid_scoring.sum())

    distance_rows = data[data["stat_name"].eq("Driving Distance")].drop_duplicates(keys)
    result["tournament_count"] = int(
        distance_rows[["event_date", "tournament"]].drop_duplicates().shape[0]
    )
    result["player_count"] = int(distance_rows["player"].nunique())
    return result


def plot_trends(summary: pd.DataFrame, charts_dir: Path) -> None:
    summary = summary.sort_values("season").reset_index(drop=True)
    charts_dir.mkdir(parents=True, exist_ok=True)
    years = summary["season"]
    latest_year = int(years.iloc[-1])
    latest_date = summary["data_through"].iloc[-1]

    figure, axes = plt.subplots(3, 2, figsize=(14, 11), layout="constrained")
    figure.patch.set_facecolor("#f7f6f2")
    for axis, (column, (title, unit, color)) in zip(axes.flat, METRIC_LABELS.items()):
        values = summary[column]
        axis.set_facecolor("#f7f6f2")
        axis.plot(
            years.iloc[:-1],
            values.iloc[:-1],
            color=color,
            linewidth=2.2,
            marker="o",
            markersize=3.8,
        )
        if len(summary) > 1:
            axis.plot(
                years.iloc[-2:],
                values.iloc[-2:],
                color=color,
                linewidth=1.8,
                linestyle="--",
                marker="o",
                markersize=4,
            )
            axis.scatter(
                [latest_year],
                [values.iloc[-1]],
                s=42,
                facecolors="#f7f6f2",
                edgecolors=color,
                linewidths=1.8,
                zorder=4,
            )
        axis.set_title(title, loc="left", fontweight="bold", color="#111111", fontsize=12)
        axis.set_ylabel(unit, color="#111111", fontsize=9)
        axis.set_xticks(years.iloc[::2])
        axis.set_xlim(years.min() - 0.5, years.max() + 0.5)
        axis.spines[["top", "right"]].set_visible(False)
        axis.spines[["left", "bottom"]].set_color("#a9aaa6")
        axis.tick_params(colors="#111111", labelsize=8)
        for label in axis.get_xticklabels() + axis.get_yticklabels():
            label.set_fontweight("bold")

    figure.suptitle(
        "PGA TOUR | How the game has changed",
        x=0.04,
        ha="left",
        fontsize=19,
        fontweight="bold",
        color="#111111",
    )
    figure.text(
        0.04,
        0.965,
        f"2004-2024 full seasons   |   {latest_year} is partial through {latest_date} (dashed)",
        color="#333333",
        fontsize=10,
    )
    output_path = charts_dir / "tour_evolution_overview.png"
    figure.savefig(output_path, dpi=300, facecolor=figure.get_facecolor())
    plt.close(figure)
    print(f"Chart: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Summarize long-term changes in PGA Tour playing styles and outcomes."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("PGA Tour Stats Analysis"))
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    data_files = sorted(data_dir.glob("pga_tour_stats_*.csv.gz"))
    if not data_files:
        parser.error(f"No prepared yearly datasets found in {data_dir}")

    summary = pd.DataFrame([summarize_year(path) for path in data_files]).sort_values("season")
    summaries_dir = data_dir / "Summaries"
    summaries_dir.mkdir(parents=True, exist_ok=True)
    summary_path = summaries_dir / "tour_evolution_annual.csv"
    summary.to_csv(summary_path, index=False, float_format="%.3f")
    plot_trends(summary, data_dir / "Charts")
    print(f"Summary: {summary_path}")

    first = summary.iloc[0]
    full_seasons = summary[summary["season"].lt(summary["season"].max())]
    last = full_seasons.iloc[-1]
    for column, (title, unit, _) in METRIC_LABELS.items():
        print(
            f"{title}: {first[column]:.3f} -> {last[column]:.3f} {unit} "
            f"({last['season'] - first['season']} seasons)"
        )


if __name__ == "__main__":
    main()