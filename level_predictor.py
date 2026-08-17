"""Predicts a starting difficulty level for a child.

The model is a scikit-learn pipeline trained by ``ml_model.py``. It is trained
to output a Level *name* ('BEGINNER' / 'INTERMEDIATE' / 'ADVANCED') directly, so
callers get a ``Level`` back rather than an opaque number.
"""
import logging
import traceback
from pathlib import Path

import joblib
import pandas as pd

from config import db
from models.child import Child, Level

logger = logging.getLogger(__name__)

FEATURE_COLUMNS = ['age', 'gender', 'race_ethnicity', 'lunch_type',
                   'parent_education', 'stem_code']

# Load the model once when the module is imported
current_dir = Path(__file__).resolve().parent
model_path = current_dir / 'level_prediction_model.joblib'
try:
    model = joblib.load(model_path)
except Exception as e:
    logger.error(f"Failed to load the model: {e}")
    model = None


def _normalise(value):
    """Match the casing the model was trained with."""
    if value is None:
        return 'unknown'
    return str(value).strip().lower()


def _child_features(child):
    """Build the one-row frame the pipeline expects from a Child instance."""
    lunch = child.lunch_type.value if child.lunch_type is not None else None
    # The children table stores the enum *name* ('BACHELORS_DEGREE'); the model
    # was trained on the human-readable value ("bachelor's degree").
    education = child.parent_education.value if child.parent_education is not None else None

    # The strand of the child's most recent attempt; brand new children have none.
    stem_code = 'unknown'
    results = sorted(
        child.results,
        key=lambda r: (r.date_acquired is not None, r.date_acquired),
        reverse=True,
    )
    for result in results:
        if result.activity is not None and result.activity.stem_code is not None:
            stem_code = result.activity.stem_code.name
            break

    return pd.DataFrame([{
        'age': int(child.age or 0),
        'gender': _normalise(child.gender),
        'race_ethnicity': _normalise(child.race_ethnicity),
        'lunch_type': _normalise(lunch),
        'parent_education': _normalise(education),
        'stem_code': _normalise(stem_code),
    }], columns=FEATURE_COLUMNS)


def predict_child_level(child_id):
    """Return a ``Level`` for the child, or ``None`` if prediction is not possible."""
    try:
        if model is None:
            raise ValueError("Model not loaded")

        # Read through the ORM session. The original opened a second connection
        # via pd.read_sql, which could not see a child that had only been
        # flushed and not yet committed -- exactly the case during signup.
        child = db.session.get(Child, child_id)
        if child is None:
            raise ValueError(f"No data found for child_id: {child_id}")

        prediction = model.predict(_child_features(child))[0]
        level = Level.coerce(prediction)
        if level is None:
            raise ValueError(f"Model returned an unusable level: {prediction!r}")
        return level
    except Exception as e:
        logger.error(f"Error in predict_child_level: {e}")
        logger.debug(traceback.format_exc())
        return None


def update_child_level(child_id):
    """Re-predict and persist ``Child.recommended_level``.

    Returns ``(success, level)``.
    """
    try:
        predicted_level = predict_child_level(child_id)
        if predicted_level is None:
            raise ValueError(f"Failed to predict level for child_id: {child_id}")

        child = db.session.get(Child, child_id)
        if child is None:
            raise ValueError(f"Child not found for child_id: {child_id}")

        child.recommended_level = predicted_level
        db.session.commit()
        logger.info(f"Updated level for child_id: {child_id} to {predicted_level.name}")
        return True, predicted_level
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating child level: {e}")
        logger.debug(traceback.format_exc())
        return False, None
