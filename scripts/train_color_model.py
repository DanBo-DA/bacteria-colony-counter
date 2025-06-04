import argparse
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib


def main():
    parser = argparse.ArgumentParser(description="Treina modelo de classificação de cor")
    parser.add_argument("csv", help="Arquivo CSV com colunas h,s,v,label")
    parser.add_argument("saida", help="Arquivo para salvar o modelo treinado")
    parser.add_argument(
        "--include-backend-data",
        action="store_true",
        help="Inclui dados de HSV gerados pelo backend (analysis_hsv_log.csv e feedback_data.csv)",
    )
    args = parser.parse_args()

    dados = pd.read_csv(args.csv)
    if args.include_backend_data:
        for extra in ["backend/analysis_hsv_log.csv", "backend/feedback_data.csv"]:
            try:
                df_extra = pd.read_csv(extra)
                dados = pd.concat([dados, df_extra], ignore_index=True)
            except FileNotFoundError:
                continue
        dados = dados.drop_duplicates()
    X = dados[["h", "s", "v"]]
    y = dados["label"]

    clf = RandomForestClassifier(n_estimators=200, random_state=42)
    clf.fit(X, y)

    joblib.dump(clf, args.saida)
    print(f"Modelo salvo em {args.saida}")


if __name__ == "__main__":
    main()
