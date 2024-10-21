import pandas as pd
import numpy as np
import os
import joblib
from sklearn.impute import SimpleImputer
from pathlib import Path
from sqlalchemy import create_engine
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, classification_report

# Connect to your database
current_dir = Path(__file__).resolve().parent
db_path = current_dir / 'instance' / 'kai_konane.db'
db_uri = f'sqlite:///{db_path.absolute()}'
engine = create_engine(db_uri)


# Load data from your database
query = """
SELECT c.id, c.age, c.gender, c.race_ethnicity, c.lunch_type, p.education_level as parent_education,
       r.score, a.stem_code
FROM children c
JOIN parents p ON c.parent_id = p.id
JOIN Results r ON c.id = r.child_id
JOIN Activity a ON r.activity_id = a.id
"""
try:
    db_data = pd.read_sql(query, engine)
except Exception as e:
    print(f"Error reading from database: {e}")
    print("Using empty DataFrame for db_data")
    db_data = pd.DataFrame(columns=['id', 'age', 'gender', 'race_ethnicity', 'lunch_type', 'parent_education', 'score', 'stem_code'])

# Load the Students Performance dataset
try:
    students_data = pd.read_csv('StudentsPerformance.csv')
except FileNotFoundError:
    print("StudentsPerformance.csv not found. Using empty DataFrame.")
    students_data = pd.DataFrame(columns=['age', 'gender', 'race_ethnicity', 'lunch_type', 'parent_education', 'score', 'stem_code'])

# Combine the datasets (you may need to adjust this based on the actual data)
combined_data = pd.concat([db_data, students_data], axis=0, ignore_index=True)

if combined_data.empty:
    print("No data available. Cannot train the model.")
else:
    # Data cleaning steps
    # 1. Remove rows with all NaN values
    combined_data = combined_data.dropna(how='all')
    
    # 2. Handle missing values
    numeric_columns = ['age', 'score']
    categorical_columns = ['gender', 'race_ethnicity', 'lunch_type', 'parent_education', 'stem_code']
    
    # Impute missing numeric values with median
    for col in numeric_columns:
        median_value = combined_data[col].median()
        if pd.notnull(median_value):
            combined_data[col] = combined_data[col].fillna(median_value)
        else:
            # If median is NaN, use 0 or another appropriate value
            combined_data[col] = combined_data[col].fillna(0)
    
    # Impute missing categorical values with mode or 'Unknown'
    for col in categorical_columns:
        mode_value = combined_data[col].mode()
        if not mode_value.empty:
            combined_data[col] = combined_data[col].fillna(mode_value[0])
        else:
            # If mode is empty, use 'Unknown' or another appropriate value
            combined_data[col] = combined_data[col].fillna('Unknown')
    
    # 3. Convert 'score' to numeric, replacing any non-numeric values with NaN
    combined_data['score'] = pd.to_numeric(combined_data['score'], errors='coerce')
    
    # 4. Remove any remaining rows with NaN in the 'score' column
    combined_data = combined_data.dropna(subset=['score'])
    
    # Print some information about the cleaned data
    print("Data shape after cleaning:", combined_data.shape)
    print("\nColumns with missing values:")
    print(combined_data.isnull().sum())
    
    # Define features and target
    X = combined_data[['age', 'gender', 'race_ethnicity', 'lunch_type', 'parent_education', 'stem_code']]
    y = combined_data['score']

    # Split the data
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    # Define preprocessing for numeric and categorical data
    numeric_features = ['age']
    categorical_features = ['gender', 'race_ethnicity', 'lunch_type', 'parent_education', 'stem_code']

    preprocessor = ColumnTransformer(
        transformers=[
            ('num', Pipeline([
                ('imputer', SimpleImputer(strategy='median')),
                ('scaler', StandardScaler())
            ]), numeric_features),
            ('cat', Pipeline([
                ('imputer', SimpleImputer(strategy='constant', fill_value='Unknown')),
                ('onehot', OneHotEncoder(handle_unknown='ignore'))
            ]), categorical_features)
        ])

    # Create a pipeline
    model = Pipeline([
        ('preprocessor', preprocessor),
        ('classifier', RandomForestClassifier(n_estimators=100, random_state=42))
    ])

    # Fit the model
    model.fit(X_train, y_train)

    # Make predictions on the test set
    y_pred = model.predict(X_test)

    # Evaluate the model
    print("Accuracy:", accuracy_score(y_test, y_pred))
    print("\nClassification Report:\n", classification_report(y_test, y_pred))

    # Save the model
    joblib.dump(model, 'level_prediction_model.joblib')
    print("Model saved as 'level_prediction_model.joblib'")