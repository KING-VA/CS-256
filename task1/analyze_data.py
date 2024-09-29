import csv
import click
import pandas as pd
import matplotlib.pyplot as plt

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
            if result in ("timeout","missing", "incorrect"): # 'incorrect' will break the program -- there is something wrong with the optimization if this shows up -- not sure what missing is?????
                continue
            runs.add(run)
            data[(benchmark, run)] = int(result)

        # Create csv
        with open("output.csv", "w") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(header + ["removed instructions", "percent removed"])
            print(",".join(header[:] + ["removed instructions", "percent removed"]))
            for (benchmark, run), result in sorted(data.items()):
                removed = data[(benchmark, "baseline")] - result
                percent = removed / data[(benchmark, "baseline")]
                print(f"{benchmark},{run},{result},{removed}, {percent:.2f}")
                writer.writerow([benchmark, run, result, removed, percent])
        
        # Read in dataframe
        df = pd.read_csv("output.csv")
        # Plot the percent removed vs benchmark for each run in histogram
        fig, ax = plt.subplots()
        for run in runs:
            run_df = df[df["run"] == run]
            ax.bar(run_df["benchmark"], run_df["percent removed"], label=run)
        ax.set_ylabel("Percent Removed")
        ax.set_xlabel("Benchmark")
        ax.set_title("Percent Removed vs Benchmark")
        ax.legend()
        plt.show()

if __name__ == "__main__":
    main()
