import os

def load_dataset(file: str) -> list:
    csv_file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), file + ".csv"))

    with open(csv_file_path, "r") as file:
        data = file.readlines()
        return [
            {
                "conversation": line.strip().split(",")[0].replace('"', "").replace("\\n", "\n"),
                "target": line.strip().split(",")[1].replace('"', "").replace("\\n", "\n")
            }
            for line in data[1:]
        ]

if __name__ == "__main__":
    print(load_dataset("triage-testing"))