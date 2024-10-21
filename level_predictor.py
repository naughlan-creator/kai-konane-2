import joblib
from pathlib import Path
import pandas as pd
from config import db, app
from models.child import Child, Level
import logging
from flask import current_app
import traceback

# Load the model once when the module is imported
current_dir = Path(__file__).resolve().parent
model_path = current_dir / 'level_prediction_model.joblib'
try:
    model = joblib.load(model_path)
except Exception as e:
    logging.error(f"Failed to load the model: {e}")
    model = None

def predict_child_level(child_id):
    try:
        if model is None:
            raise ValueError("Model not loaded")

        query = """
        SELECT c.age, c.gender, c.race_ethnicity, c.lunch_type, p.education_level as parent_education,
           CASE 
               WHEN a.stem_code IS NULL THEN 'UNKNOWN'
               ELSE CAST(a.stem_code AS CHAR)
           END as stem_code
        FROM children c
        JOIN parents p ON c.parent_id = p.id
        LEFT JOIN results r ON c.id = r.child_id
        LEFT JOIN activity a ON r.activity_id = a.id
        WHERE c.id = %s
        LIMIT 1
        """

        with app.app_context():
            child_data = pd.read_sql(query, db.engine, params=(child_id,))

        if child_data.empty:
            raise ValueError(f"No data found for child_id: {child_id}")

        required_columns = ['age', 'gender', 'race_ethnicity', 'lunch_type', 'parent_education', 'stem_code']
        for col in required_columns:
            if col not in child_data.columns:
                child_data[col] = 'UNKNOWN'

        # Ensure data types match model expectations
        child_data['age'] = child_data['age'].astype(int)
        categorical_columns = ['gender', 'race_ethnicity', 'lunch_type', 'parent_education', 'stem_code']
        child_data[categorical_columns] = child_data[categorical_columns].astype('category')

        predicted_level = model.predict(child_data)
        return predicted_level[0]
    except Exception as e:
        current_app.logger.error(f"Error in predict_child_level: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return None

def update_child_level(child_id):
    try:
        predicted_level = predict_child_level(child_id)
        
        if predicted_level is None:
            raise ValueError(f"Failed to predict level for child_id: {child_id}")

        level_mapping = {0: Level.BEGINNER, 1: Level.INTERMEDIATE, 2: Level.ADVANCED}
        recommended_level = level_mapping.get(predicted_level, Level.BEGINNER)

        with app.app_context():
            child = Child.query.get(child_id)
            if child:
                child.recommended_level = recommended_level
                db.session.commit()
                current_app.logger.info(f"Updated level for child_id: {child_id} to {recommended_level}")
                return True, recommended_level
            else:
                raise ValueError(f"Child not found for child_id: {child_id}")
    except Exception as e:
        current_app.logger.error(f"Error updating child level: {str(e)}")
        current_app.logger.error(traceback.format_exc())
        return False, None