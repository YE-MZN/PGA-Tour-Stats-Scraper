import argparse
import csv
import gzip
import io
import zipfile
from pathlib import Path, PurePosixPath


METADATA_COLUMNS = [
    "season",
    "event_date",
    "tournament",
    "category",
    "subcategory",
    "stat_name",
    "rank",
    "player",
    "source_file",
]


def get_source_metadata(member_name: str, season: int) -> dict[str, str] | None:
    parts = PurePosixPath(member_name).parts
    if len(parts) != 5 or parts[0] != str(season):
        return None

    event_parts = parts[1].split(", ", 1)
    stat_parts = Path(parts[4]).stem.split(", ", 1)
    if len(event_parts) != 2 or len(stat_parts) != 2:
        return None

    return {
        "season": str(season),
        "event_date": event_parts[0],
        "tournament": event_parts[1],
        "category": parts[2],
        "subcategory": parts[3],
        "stat_name": stat_parts[1],
        "source_file": member_name,
    }


def read_csv_header(archive: zipfile.ZipFile, member_name: str) -> list[str]:
    with archive.open(member_name) as source:
        with io.TextIOWrapper(source, encoding="utf-8-sig", newline="") as text:
            return next(csv.reader(text), [])


def write_analysis_data(archive_path: Path, output_dir: Path, season: int) -> None:
    output_path = output_dir / f"pga_tour_stats_{season}.csv.gz"
    output_dir.mkdir(parents=True, exist_ok=True)
    row_count = 0
    source_count = 0

    with zipfile.ZipFile(archive_path) as archive:
        members = [
            info.filename
            for info in archive.infolist()
            if not info.is_dir()
            and info.filename.lower().endswith(".csv")
            and get_source_metadata(info.filename, season) is not None
        ]
        metric_columns = set()
        for member_name in members:
            metric_columns.update(
                f"metric__{column}"
                for column in read_csv_header(archive, member_name)
                if column not in {"rank", "player"}
            )

        fieldnames = METADATA_COLUMNS + sorted(metric_columns)
        with gzip.open(output_path, "wt", encoding="utf-8", newline="") as output:
            writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
            writer.writeheader()

            for member_name in members:
                metadata = get_source_metadata(member_name, season)
                with archive.open(member_name) as source:
                    with io.TextIOWrapper(source, encoding="utf-8-sig", newline="") as text:
                        for row in csv.DictReader(text):
                            record = metadata | {
                                "rank": row.get("rank", ""),
                                "player": row.get("player", ""),
                            }
                            record.update(
                                {
                                    f"metric__{column}": value
                                    for column, value in row.items()
                                    if column not in {"rank", "player"} and column is not None
                                }
                            )
                            writer.writerow(record)
                            row_count += 1
                source_count += 1

    print(f"{season}: {source_count:,} CSV files, {row_count:,} rows -> {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Combine the archived PGA Tour stat CSV files into analysis-ready yearly datasets."
    )
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        help="Years to process (default: every year with a ZIP archive).",
    )
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("PGA Tour Event Stats"),
        help="Directory containing yearly ZIP archives.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("PGA Tour Stats Analysis"),
        help="Directory for the generated CSV.GZ files.",
    )
    args = parser.parse_args()

    source_dir = args.source_dir.resolve()
    output_dir = args.output_dir.resolve()
    years = args.years or sorted(
        int(path.stem) for path in source_dir.glob("*.zip") if path.stem.isdigit()
    )
    for season in years:
        archive_path = source_dir / f"{season}.zip"
        if not archive_path.is_file():
            parser.error(f"Archive not found: {archive_path}")
        write_analysis_data(archive_path, output_dir, season)


if __name__ == "__main__":
    main()