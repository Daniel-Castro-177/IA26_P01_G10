from pathlib import Path
import pandas as pd

tiny_dir = Path("data/data_tiny_30_31oct2026")
tiny_data = {
    file.stem: pd.read_csv(file)
    for file in tiny_dir.glob("*.csv")
}

for nome, tabela in tiny_data.items():
    print(f"\n--- Ficheiro: {nome} ---")
    print(tabela.head(3))