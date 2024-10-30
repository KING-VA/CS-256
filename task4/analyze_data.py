import csv
import click
import pandas as pd
import matplotlib.pyplot as plt

PATH_NAMES = ['benchmarks_ssa']

def combineFiles():
    # Combine the files
    with open("merged.csv", "w") as csvfile:
        writer = csv.writer(csvfile)
        first = True
        for path in PATH_NAMES:
            with open(f"{path}.csv", "r") as file:
                reader = csv.reader(file)
                if not first:
                    next(reader)
                for row in reader:
                    if len(row) != 0:
                        writer.writerow(row)
                first = False

# @click.command()
# @click.argument("csv_path", metavar="CSVFILE", type=click.Path(exists=True))
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
                try:
                    removed = data[(benchmark, "baseline")] - result
                    percent = removed / data[(benchmark, "baseline")]
                    print(f"{benchmark},{run},{result},{removed}, {percent:.2f}")
                    if run != "baseline":
                        writer.writerow([benchmark, run, result, removed, percent])
                except:
                    continue
        
        # Read in dataframe
        df = pd.read_csv("output.csv")
        # Sort the df by percent removed
        df = df.sort_values(by="percent removed", ascending=False)
        # Save to csv
        df.to_csv("output.csv", index=False)
        # Trim the df to only include the top 10 benchmarks and the bottom 5 benchmarks
        df = pd.concat([df.head(5), df.tail(5)])
        # Sort df by percent removed
        df = df.sort_values(by="percent removed", ascending=False)
        # Plot the percent removed vs benchmark for each run in histogram
        fig, ax = plt.subplots()
        # Set figure size
        fig.set_size_inches(20, 10)
        for run in runs:
            run_df = df[df["run"] == run]
            if len(run_df) != 0:
                ax.bar(run_df["benchmark"], run_df["percent removed"], label=run)
        ax.set_ylabel("Percent Removed")
        ax.set_xlabel("Benchmark")
        ax.set_title("Percent Removed vs Benchmark")
        ax.legend()
        plt.savefig("output_percent_removed.png")

        # Create a plot which shows distribution of percent removed
        df = pd.read_csv("output.csv")
        fig, ax = plt.subplots()
        fig.set_size_inches(10, 10)
        ax.hist(df["percent removed"], bins=10)
        ax.set_ylabel("Number of Benchmarks")
        ax.set_xlabel("Percent Removed")
        ax.set_title("Distribution of Percent Removed")
        plt.savefig("output_distribution.png")
        plt.show()

if __name__ == "__main__":
    combineFiles()
    main("merged.csv")
