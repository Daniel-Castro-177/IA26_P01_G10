from pathlib import Path

import pandas as pd

DATA_DIR = Path("data/data_tiny_30_31oct2026")

pd.set_option("display.width", 200)
pd.set_option("display.max_columns", None)

localities = pd.read_csv(DATA_DIR / "localities.csv")
locations = pd.read_csv(DATA_DIR / "locations.csv")
distance_matrix = pd.read_csv(DATA_DIR / "distance_matrix.csv")
producers = pd.read_csv(DATA_DIR / "producers.csv")
products = pd.read_csv(DATA_DIR / "products.csv")
collection_centers = pd.read_csv(DATA_DIR / "collection_centers.csv")
vehicles = pd.read_csv(DATA_DIR / "vehicles.csv")
customers = pd.read_csv(DATA_DIR / "customers.csv")
delivery_locations = pd.read_csv(DATA_DIR / "delivery_locations.csv")
orders = pd.read_csv(DATA_DIR / "orders.csv", parse_dates=["order_datetime"])
order_items = pd.read_csv(
    DATA_DIR / "order_items.csv",
    parse_dates=["availability_start", "availability_end", "delivery_start", "delivery_end"],
)
rules = pd.read_csv(DATA_DIR / "rules.csv")

if __name__ == "__main__":
    tabelas = {
        "localities": localities,
        "locations": locations,
        "distance_matrix": distance_matrix,
        "producers": producers,
        "products": products,
        "collection_centers": collection_centers,
        "vehicles": vehicles,
        "customers": customers,
        "delivery_locations": delivery_locations,
        "orders": orders,
        "order_items": order_items,
        "rules": rules,
    }

    for nome, tabela in tabelas.items():
        print(f"=== {nome} {tabela.shape} ===")
        print(tabela.head())
        print()

    print(order_items.dtypes)