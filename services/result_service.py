from models.result import Result
from config import db

class ResultService:
    def __init__(self):
        self.db = db
    
    def create_result(self, child_id, activity_id, score):
        result = Result(child_id, activity_id, score)
        self.db.session.add(result)
        self.db.session.commit()
        return result
    
    def get_result(self, result_id):
        return Result.query.get(result_id)
    
    def get_results_by_child(self, child_id):
        return Result.query.filter_by(child_id=child_id).all()
    
    def get_results_by_activity(self, activity_id):
        return Result.query.filter_by(activity_id=activity_id).all()
    
    def get_all_results():
        return Result.query.all()
    
    def update_result(self, result_id, new_score):
        result = self.get_result(result_id)
        if result:
            result.score = new_score
            self.db.session.commit()
            return "Result updated successfully"
        return "Result not found"
    
    def delete_result(self, result_id):
        result = self.get_result(result_id)
        if result:
            self.db.session.delete(result)
            self.db.session.commit()
            return "Result deleted successfully"
        return "Result not found"
    
    def get_results_by_teacher(self, teacher_id):
        from models.child import Child
        children = Child.query.filter_by(teacher_id=teacher_id).all()
        results = []
        for child in children:
            results.extend(self.get_results_by_child(child.id))
        return results