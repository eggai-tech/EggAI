import os
import csv


def load_dataset(file: str) -> list:
    # Construct the absolute path to the CSV file
    csv_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), file + ".csv"))

    # Open the CSV file and parse it using the csv.DictReader
    with open(csv_file_path, "r", newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        data = []

        for row in reader:
            data.append({
                "conversation": row["conversation"].replace("\\n", "\n"),
                "target": row["target"]
            })

        return data

if __name__ == "__main__":
    print(load_dataset("triage-testing"))