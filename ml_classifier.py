import pandas as pd
import joblib
import os
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split

MODEL_PATH = "models/smc_rf.pkl"

def train_model(csv_path: str):
    """
    Train a RandomForest model based on historical labeled data.
    """
    if not os.path.exists("models"):
        os.makedirs("models")
        
    df = pd.read_csv(csv_path)
    # Features: open, high, low, close, tick_volume, OBs, BOSs, Sweeps
    # Target: 'label' (1 for win, 0 for loss)
    
    if "label" not in df.columns:
        print("❌ Error: CSV must contain a 'label' column (1 for win, 0 for loss)")
        return

    features = [c for c in df.columns if c not in ["label", "time", "date"]]
    X = df[features]
    y = df["label"]

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )

    clf = RandomForestClassifier(
        n_estimators=400,
        max_depth=10,
        min_samples_leaf=4,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    clf.fit(X_train, y_train)

    acc = clf.score(X_test, y_test)
    print(f"✅ Model trained - Test accuracy: {acc:.3%}")

    joblib.dump(clf, MODEL_PATH)
    print(f"📦 Model saved to {MODEL_PATH}")

def load_model():
    if not os.path.exists(MODEL_PATH):
        # Return a dummy classifier or handle if not trained
        return None
    return joblib.load(MODEL_PATH)

def predict_signal(df_row: pd.DataFrame) -> float:
    """
    Predict the probability of a successful trade.
    """
    model = load_model()
    if model is None:
        return 1.0 # Default to 1.0 if no model exists
    
    # Ensure features match
    features = model.feature_names_in_
    X = df_row[features]
    
    prob = model.predict_proba(X)[:, 1][0]
    return prob
