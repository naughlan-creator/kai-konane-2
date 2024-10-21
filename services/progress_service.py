from models.progress import Progress
from config import db

class ProgressService:
    def __init__(self):
        self.db = db

    def add_progress(self, child_id, learning_content_id, total_num_questions):
        new_progress = Progress(
            child_id=child_id, 
            learning_content_id=learning_content_id, 
            total_num_questions=total_num_questions
        )
        self.db.session.add(new_progress)
        self.db.session.commit()
        return new_progress


    def get_progress(self, progress_id):
        return Progress.query.get(progress_id)

    def get_progresses():
        return Progress.query.all()

    def update_progress(self, progress_id, new_rate):
        progress = self.get_progress(progress_id)
        if progress:
            progress.update_completion_rate(new_rate)
            return "Progress updated!!!"
        return "Progress not updated!!!"

    def mark_as_completed(self, progress_id):
        progress = self.get_progress(progress_id)
        if progress:
            progress.mark_as_completed()
            return "Progress marked as completed!!!"
        return "Progress not marked as completed!!!"
    
    def get_progress_by_child(self, child_id):
        return Progress.query.filter_by(child_id=child_id).all()

    def get_progress_by_teacher(self, teacher_id):
        from models.child import Child
        children = Child.query.filter_by(teacher_id=teacher_id).all()
        progress = []
        for child in children:
            progress.extend(self.get_progress_by_child(child.id))
        return progress