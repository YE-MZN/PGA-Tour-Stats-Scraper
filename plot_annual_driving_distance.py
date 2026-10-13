import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def summarize_year(path: Path) -> dict[str, int | float | str | bool]:
    columns = {
        "season",
        "event_date",
        "tournament",
        "player",
        "stat_name",
        "metric__Avg",
        "metric__Total Distance",
        "metric__Total Drives",
    }
    data = pd.read_csv(path, usecols=lambda column: column in columns, low_memory=False)
    data = data[data["stat_name"].eq("Driving Distance")].drop_duplicates(
        ["season", "event_date", "tournament", "player"]
    )
    data["average"] = pd.to_numeric(data["metric__Avg"], errors="coerce")
    data["total_distance"] = pd.to_numeric(
        data["metric__Total Distance"].str.replace(",", "", regex=False),
        errors="coerce",
    )
    data["total_drives"] = pd.to_numeric(data["metric__Total Drives"], errors="coerce")
    data = data.dropna(subset=["average", "total_distance", "total_drives"])
    data = data[data["total_drives"].gt(0)]

    season = int(path.name.split("_")[-1].split(".")[0])
    return {
        "season": season,
        "driving_distance_weighted_mean": data["total_distance"].sum()
        / data["total_drives"].sum(),
        "player_event_median": data["average"].median(),
        "player_event_p25": data["average"].quantile(0.25),
        "player_event_p75": data["average"].quantile(0.75),
        "player_event_count": len(data),
        "tournament_count": data[["event_date", "tournament"]].drop_duplicates().shape[0],
        "measured_drives": int(data["total_drives"].sum()),
        "data_through": data["event_date"].max(),
    }


def create_chart(summary: pd.DataFrame, charts_dir: Path, summaries_dir: Path) -> None:
    summary = summary.sort_values("season").reset_index(drop=True)
    latest_year = summary["season"].max()
    previous_event_counts = summary.loc[summary["season"].lt(latest_year), "tournament_count"]
    is_partial = summary["tournament_count"].iloc[-1] < previous_event_counts.median() * 0.5
    summary["partial_season"] = False
    if is_partial:
        summary.loc[summary.index[-1], "partial_season"] = True

    charts_dir.mkdir(parents=True, exist_ok=True)
    summaries_dir.mkdir(parents=True, exist_ok=True)
    summary.to_csv(summaries_dir / "annual_driving_distance.csv", index=False, float_format="%.2f")

    figure, axis = plt.subplots(figsize=(12, 6.5), layout="constrained")
    figure.patch.set_facecolor("#f7f6f2")
    axis.set_facecolor("#f7f6f2")
    axis.fill_between(
        summary["season"],
        summary["player_event_p25"],
        summary["player_event_p75"],
        color="#dce8e4",
        alpha=0.8,
        label="Player-event 25th-75th percentile",
    )
    axis.plot(
        summary["season"],
        summary["driving_distance_weighted_mean"],
        color="#bd4d34",
        marker="o",
        markersize=4.5,
        linewidth=2.5,
        label="Drive-weighted mean",
    )
    axis.plot(
        summary["season"],
        summary["player_event_median"],
        color="#176c68",
        linestyle="--",
        marker="s",
        markersize=3.5,
        linewidth=1.5,
        label="Player-event median",
    )
    if is_partial:
        latest = summary.iloc[-1]
        axis.annotate(
            f"Partial season through {latest['data_through']}",
            (latest["season"], latest["driving_distance_weighted_mean"]),
            xytext=(-10, 20),
            textcoords="offset points",
            ha="right",
            fontsize=9,
            color="#111111",
            fontweight="bold",
        )

    axis.set_title(
        "PGA TOUR | Driving distance by season",
        loc="left",
        fontsize=16,
        fontweight="bold",
        color="#111111",
        pad=14,
    )
    axis.set_xlabel("Season", fontweight="bold", color="#111111")
    axis.set_ylabel("Driving distance (yards)", fontweight="bold", color="#111111")
    axis.set_xticks(summary["season"][::2])
    axis.set_xlim(summary["season"].min() - 0.5, summary["season"].max() + 0.5)
    y_min = min(270, int(summary["player_event_p25"].min() // 5 * 5))
    y_max = max(315, int((summary["player_event_p75"].max() + 4) // 5 * 5))
    axis.set_ylim(y_min, y_max)
    axis.set_yticks(range(y_min, y_max + 1, 5))
    axis.spines[["top", "right"]].set_visible(False)
    axis.spines[["left", "bottom"]].set_color("#a9aaa6")
    axis.tick_params(colors="#111111", labelsize=9)
    for label in axis.get_xticklabels() + axis.get_yticklabels():
        label.set_fontweight("bold")
    axis.legend(frameon=False, loc="upper left", ncol=3, fontsize=9)

    charts_path = charts_dir / "annual_driving_distance.png"
    figure.savefig(charts_path, dpi=300, facecolor=figure.get_facecolor())
    plt.close(figure)
    print(f"Chart: {charts_path}")
    print(f"Summary: {summaries_dir / 'annual_driving_distance.csv'}")
    first = summary.iloc[0]
    latest = summary.iloc[-1]
    print(
        f"Weighted mean: {first['season']} {first['driving_distance_weighted_mean']:.2f} yd "
        f"to {latest['season']} {latest['driving_distance_weighted_mean']:.2f} yd"
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot annual PGA Tour driving-distance trends from prepared datasets."
    )
    parser.add_argument("--data-dir", type=Path, default=Path("PGA Tour Stats Analysis"))
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    data_files = sorted(data_dir.glob("pga_tour_stats_*.csv.gz"))
    if not data_files:
        parser.error(f"No prepared yearly datasets found in {data_dir}")
    summary = pd.DataFrame([summarize_year(path) for path in data_files])
    create_chart(summary, data_dir / "Charts", data_dir / "Summaries")


if __name__ == "__main__":
    main()