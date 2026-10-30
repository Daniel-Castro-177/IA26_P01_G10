from pathlib import Path
import pandas as pd

small_dir = Path("data/data_small_30_31oct2026")
tiny_dir = Path("data/data_tiny_30_31oct2026")

small_data = {
    file.stem: pd.read_csv(file)
    for file in small_dir.glob("*.csv")
}

tiny_data = {
    file.stem: pd.read_csv(file)
    for file in tiny_dir.glob("*.csv")
}