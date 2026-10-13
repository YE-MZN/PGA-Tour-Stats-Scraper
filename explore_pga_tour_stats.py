import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


def load_analysis_data(path: Path) -> pd.DataFrame:
    columns = {
        "event_date",
        "tournament",
        "player",
        "stat_name",
        "metric__Avg",
        "metric__%",
    }
    data = pd.read_csv(path, usecols=lambda column: column in columns, low_memory=False)
    data = data[
        data["stat_name"].isin(
            [
                "SG Tee To Green",
                "SG Putting",
                "SG Total",
                "Driving Distance",
                "Driving Accuracy Percentage",
            ]
        )
    ].copy()
    data["value"] = pd.to_numeric(data["metric__Avg"], errors="coerce")
    accuracy = data["stat_name"].eq("Driving Accuracy Percentage")
    data.loc[accuracy, "value"] = pd.to_numeric(
        data.loc[accuracy, "metric__%"].str.rstrip("%"), errors="coerce"
    )

    keys = ["event_date", "tournament", "player"]
    return data.pivot_table(
        index=keys,
        columns="stat_name",
        values="value",
        aggfunc="mean",
    ).reset_index()


def correlation(data: pd.DataFrame, x_column: str, y_column: str) -> tuple[pd.DataFrame, float]:
    paired = data[[x_column, y_column]].dropna()
    return paired, float(paired[x_column].corr(paired[y_column]))


def add_trend_line(axis: plt.Axes, data: pd.DataFrame, x_column: str, y_column: str) -> None:
    x_values = data[x_column].to_numpy()
    slope, intercept = np.polyfit(x_values, data[y_column].to_numpy(), 1)
    line_x = np.linspace(x_values.min(), x_values.max(), 100)
    axis.plot(line_x, slope * line_x + intercept, color="#182a3a", linewidth=2)


def create_chart(data: pd.DataFrame, year: int, output_path: Path) -> None:
    sg = data.dropna(subset=["SG Tee To Green", "SG Putting", "SG Total"])
    driving = data.dropna(subset=["Driving Distance", "Driving Accuracy Percentage"])
    if sg.empty or driving.empty:
        raise ValueError(f"Not enough matched records to plot {year}.")

    figure, axes = plt.subplots(1, 2, figsize=(15, 7), layout="constrained")
    figure.patch.set_facecolor("#f7f6f2")
    for axis in axes:
        axis.set_facecolor("#f7f6f2")
        axis.spines[["top", "right"]].set_visible(False)
        axis.spines[["left", "bottom"]].set_color("#a9aaa6")
        axis.tick_params(colors="#111111", labelsize=9)
        for label in axis.get_xticklabels() + axis.get_yticklabels():
            label.set_fontweight("bold")

    first, sg_corr = correlation(sg, "SG Tee To Green", "SG Putting")
    points = axes[0].scatter(
        first["SG Tee To Green"],
        first["SG Putting"],
        c=sg.loc[first.index, "SG Total"],
        cmap="coolwarm",
        vmin=-3,
        vmax=3,
        s=19,
        alpha=0.65,
        linewidths=0,
        rasterized=True,
    )
    axes[0].axhline(0, color="#8c8d88", linewidth=0.8)
    axes[0].axvline(0, color="#8c8d88", linewidth=0.8)
    axes[0].set_xlabel("SG: Tee-to-Green per round", fontweight="bold", color="#111111")
    axes[0].set_ylabel("SG: Putting per round", fontweight="bold", color="#111111")
    axes[0].set_title("Different routes to a strong week", loc="left", fontweight="bold", color="#111111")
    axes[0].text(
        0.02,
        0.97,
        f"r = {sg_corr:.2f}  |  {len(first):,} player-event pairs",
        transform=axes[0].transAxes,
        va="top",
        color="#111111",
        fontweight="bold",
        fontsize=9,
    )

    second = driving.dropna(
        subset=["Driving Distance", "Driving Accuracy Percentage"]
    )
    drive_corr = float(
        second["Driving Distance"].corr(second["Driving Accuracy Percentage"])
    )
    colored_driving = second.dropna(subset=["SG Total"])
    axes[1].scatter(
        second.loc[second["SG Total"].isna(), "Driving Distance"],
        second.loc[second["SG Total"].isna(), "Driving Accuracy Percentage"],
        color="#a9aaa6",
        s=19,
        alpha=0.45,
        linewidths=0,
        rasterized=True,
    )
    axes[1].scatter(
        colored_driving["Driving Distance"],
        colored_driving["Driving Accuracy Percentage"],
        c=colored_driving["SG Total"],
        cmap="coolwarm",
        vmin=-3,
        vmax=3,
        s=19,
        alpha=0.65,
        linewidths=0,
        rasterized=True,
    )
    add_trend_line(axes[1], second, "Driving Distance", "Driving Accuracy Percentage")
    axes[1].set_xlabel("Driving distance (yards)", fontweight="bold", color="#111111")
    axes[1].set_ylabel("Driving accuracy (%)", fontweight="bold", color="#111111")
    axes[1].set_title("Distance vs. accuracy", loc="left", fontweight="bold", color="#111111")
    axes[1].text(
        0.02,
        0.97,
        f"r = {drive_corr:.2f}  |  {len(second):,} pairs, {len(colored_driving):,} SG-colored",
        transform=axes[1].transAxes,
        va="top",
        color="#111111",
        fontweight="bold",
        fontsize=9,
    )

    colorbar = figure.colorbar(points, ax=axes, shrink=0.82, pad=0.02)
    colorbar.set_label("SG: Total per round", fontweight="bold", color="#111111")
    colorbar.ax.tick_params(colors="#111111")
    figure.suptitle(
        f"PGA TOUR | {year} player-event snapshot",
        x=0.04,
        ha="left",
        fontsize=17,
        fontweight="bold",
        color="#111111",
    )
    figure.savefig(output_path, dpi=300, facecolor=figure.get_facecolor())
    plt.close(figure)

    print(f"Chart: {output_path}")
    print(f"SG Tee-to-Green vs Putting: r={sg_corr:.3f}, n={len(first):,}")
    print(f"Driving distance vs accuracy: r={drive_corr:.3f}, n={len(second):,}")
    print(f"Player-event records matched: {len(data):,}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Plot exploratory relationships in a prepared yearly PGA Tour dataset."
    )
    parser.add_argument("--year", type=int, default=2024)
    parser.add_argument(
        "--data-dir", type=Path, default=Path("PGA Tour Stats Analysis")
    )
    args = parser.parse_args()

    data_dir = args.data_dir.resolve()
    data_path = data_dir / f"pga_tour_stats_{args.year}.csv.gz"
    if not data_path.is_file():
        parser.error(f"Dataset not found: {data_path}")
    create_chart(
        load_analysis_data(data_path),
        args.year,
        data_dir / f"exploratory_analysis_{args.year}.png",
    )


if __name__ == "__main__":
    main()