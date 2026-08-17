"""Trains the starting-level recommendation model.

Run with:  python ml_model.py

The model predicts a Level name ('BEGINNER' / 'INTERMEDIATE' / 'ADVANCED') from a
child's background, so ``level_predictor.predict_child_level`` can turn the
output straight into a ``Level``.

Training data comes from two places:

* ``StudentsPerformance.csv`` -- a public dataset whose columns are renamed to
  the feature names used by the app. Without that rename every CSV column landed
  as NaN, the whole file was dropped, and the model was left training on one
  class -- which is why it used to predict BEGINNER for every single child.
* the app's own database, once children have actually completed activities.
"""
import os
from pathlib import Path

import joblib
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sqlalchemy import create_engine, text

current_dir = Path(__file__).resolve().parent

FEATURES = ['age', 'gender', 'race_ethnicity', 'lunch_type',
            'parent_education', 'stem_code']
NUMERIC_FEATURES = ['age']
CATEGORICAL_FEATURES = ['gender', 'race_ethnicity', 'lunch_type',
                        'parent_education', 'stem_code']

# The CSV's own column names, mapped onto the app's feature names.
CSV_COLUMN_MAP = {
    'gender': 'gender',
    'race/ethnicity': 'race_ethnicity',
    'parental level of education': 'parent_education',
    'lunch': 'lunch_type',
}

# Score thresholds used to turn a percentage into a difficulty level.
LEVEL_THRESHOLDS = ((80, 'ADVANCED'), (60, 'INTERMEDIATE'))
DEFAULT_LEVEL = 'BEGINNER'

# Median age of the app's audience; the public dataset has no age column.
ASSUMED_AGE = 5


def score_to_level(score):
    for threshold, level in LEVEL_THRESHOLDS:
        if score >= threshold:
            return level
    return DEFAULT_LEVEL


def normalise(frame):
    """Lower-case every categorical value so training matches prediction."""
    for column in CATEGORICAL_FEATURES:
        frame[column] = (frame[column].astype('string')
                         .fillna('unknown').str.strip().str.lower())
    frame['age'] = pd.to_numeric(frame['age'], errors='coerce').fillna(ASSUMED_AGE)
    return frame


def load_csv_data():
    csv_path = current_dir / 'StudentsPerformance.csv'
    try:
        raw = pd.read_csv(csv_path)
    except FileNotFoundError:
        print(f"{csv_path.name} not found. Skipping the public dataset.")
        return pd.DataFrame(columns=FEATURES + ['level'])

    missing = [c for c in CSV_COLUMN_MAP if c not in raw.columns]
    if missing:
        raise ValueError(f"{csv_path.name} is missing expected columns: {missing}")

    data = raw.rename(columns=CSV_COLUMN_MAP)
    score_columns = ['math score', 'reading score', 'writing score']
    data['score'] = data[score_columns].mean(axis=1)

    data['age'] = ASSUMED_AGE
    data['stem_code'] = 'unknown'  # the dataset is not split by STEM strand
    data['level'] = data['score'].apply(score_to_level)

    return normalise(data[FEATURES + ['level']].copy())


def load_db_data():
    """Real results from the app, if the database is reachable and populated."""
    uri = (os.getenv('DATABASE_URL') or os.getenv('JAWSDB_URL')
           or 'sqlite:///' + str(current_dir / 'instance' / 'kai_konane.db'))
    if uri.startswith('postgres://'):
        uri = uri.replace('postgres://', 'postgresql://', 1)

    query = text("""
        SELECT c.age            AS age,
               c.gender         AS gender,
               c.race_ethnicity AS race_ethnicity,
               c.lunch_type     AS lunch_type,
               p.education_level AS parent_education,
               a.stem_code      AS stem_code,
               r.score          AS score
        FROM children c
        JOIN parents p  ON c.parent_id = p.id
        JOIN results r  ON c.id = r.child_id
        JOIN activity a ON r.activity_id = a.id
    """)

    try:
        engine = create_engine(uri)
        with engine.connect() as connection:
            data = pd.read_sql(query, connection)
    except Exception as e:
        print(f"Could not read training rows from the database ({e}).")
        return pd.DataFrame(columns=FEATURES + ['level'])

    if data.empty:
        print("No completed activities in the database yet.")
        return pd.DataFrame(columns=FEATURES + ['level'])

    # The database stores enum names; the CSV supplies readable values. Map the
    # names onto the same vocabulary before they are combined.
    from models.child import EducationLevel, LunchType
    data['lunch_type'] = data['lunch_type'].map(
        lambda v: LunchType[v].value if v in LunchType.__members__ else v)
    data['parent_education'] = data['parent_education'].map(
        lambda v: EducationLevel[v].value if v in EducationLevel.__members__ else v)

    data['level'] = data['score'].apply(score_to_level)
    return normalise(data[FEATURES + ['level']].copy())


def build_pipeline():
    preprocessor = ColumnTransformer(transformers=[
        ('num', Pipeline([
            ('imputer', SimpleImputer(strategy='median')),
            ('scaler', StandardScaler()),
        ]), NUMERIC_FEATURES),
        ('cat', Pipeline([
            ('imputer', SimpleImputer(strategy='constant', fill_value='unknown')),
            ('onehot', OneHotEncoder(handle_unknown='ignore')),
        ]), CATEGORICAL_FEATURES),
    ])

    return Pipeline([
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(n_estimators=100, random_state=42)),
    ])


def main():
    frames = [frame for frame in (load_csv_data(), load_db_data()) if not frame.empty]
    if not frames:
        print("No data available. Cannot train the model.")
        return

    combined = pd.concat(frames, axis=0, ignore_index=True).dropna(subset=['level'])
    print("Training rows:", len(combined))
    print("Level distribution:\n", combined['level'].value_counts())

    if combined['level'].nunique() < 2:
        print("Only one level present in the data -- refusing to train a model "
              "that can only ever predict one answer.")
        return

    X = combined[FEATURES]
    y = combined['level']

    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y)

    model = build_pipeline()
    model.fit(X_train, y_train)

    y_pred = model.predict(X_test)
    print("\nAccuracy:", accuracy_score(y_test, y_pred))
    print("\nClassification Report:\n", classification_report(y_test, y_pred))

    output = current_dir / 'level_prediction_model.joblib'
    joblib.dump(model, output)
    print(f"Model saved as '{output.name}' (classes: {list(model.classes_)})")


if __name__ == '__main__':
    main()
