import csv
import click


@click.command()
@click.argument("csv_path", metavar="CSVFILE", type=click.Path(exists=True))
def main(csv_path):
    with open(csv_path, newline="") as csvfile:
        reader = csv.reader(csvfile, delimiter=",")
        header = next(reader)
        data: dict[tuple[str, str], int] = dict()
        runs = set()
        for row in reader:
            if len(row) == 0:
                continue
            benchmark, run, result = row
            if result in ("timeout","missing"): # 'incorrect' will break the program -- there is something wrong with the optimization if this shows up -- not sure what missing is?????
                continue
            runs.add(run)
            data[(benchmark, run)] = int(result)
        print(",".join(header[:] + ["Removed Instructions", "Percent Removed"]))
        for (benchmark, run), result in sorted(data.items()):
            removed = data[(benchmark, "baseline")] - result
            percent = removed / data[(benchmark, "baseline")]
            print(f"{benchmark}_{run},{result},{removed}, {percent:.2f}")


if __name__ == "__main__":
    main()
