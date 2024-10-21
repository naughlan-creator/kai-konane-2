import os
from werkzeug.utils import secure_filename
from models.story import Story, Level
from models.progress import Progress
from models.reward import Reward
from config import db
from models.page import Page

class StoryService:
    def __init__(self):
        self.db = db
        self.UPLOAD_FOLDER = os.path.join('static', 'images')

    def add_story(self, title, level, cover_image, pages):
        cover_filename = self._save_image(cover_image)
        new_story = Story(title=title, level=level, cover_page=cover_filename)

        for page_data in pages:
            page_image = self._save_image(page_data['image'])
            new_page = Page(
                line_of_page=page_data['line_of_page'],
                image_filename=page_image,
                is_last_page=page_data['is_last_page']
            )
            new_story.pages.append(new_page)

        self.db.session.add(new_story)
        self.db.session.commit()
        return new_story

    def get_story(self, story_id):
        return Story.query.get(story_id)

    def get_stories(self):
        return Story.query.all()

    def update_story(self, story_id, title=None, level=None, cover_image=None, pages=None):
        story = self.get_story(story_id)
        if story:
            if title:
                story.title = title
            if level:
                story.level = Level[level.upper()]
            if cover_image:
                story.cover_image = self._save_image(cover_image)
            if pages:
                # Remove existing pages
                for page in story.pages:
                    self.db.session.delete(page)
                
                # Add new pages
                for page_data in pages:
                    page_image = self._save_image(page_data['image'])
                    new_page = Page(
                        line_of_page=page_data['line_of_page'],
                        image_filename=page_image,
                        is_last_page=page_data['is_last_page']
                    )
                    story.pages.append(new_page)

    
    def add_page(self, story_id, line_of_page, is_last_page=False):
        story = self.get_story(story_id)
        if story:
            new_page = Page(line_of_page=line_of_page, is_last_page=is_last_page)
            story.pages.append(new_page)
            self.db.session.commit()
            return new_page
        return "Story not found!!!"
    
    def _save_image(self, image):
        if image:
            filename = secure_filename(image.filename)
            image.save(os.path.join(self.UPLOAD_FOLDER, filename))
            return filename
        return None
    
    def get_story_progress(self, story_id, child_id):
        progress = Progress.query.filter_by(child_id=child_id, learning_content_id=story_id).first()
        if progress:
            return progress.completion_rate
        return 0

    def save_story_progress(self, story_id, child_id, current_page):
        story = self.get_story(story_id)
        if not story:
            return None, "Story not found"

        progress = Progress.query.filter_by(child_id=child_id, learning_content_id=story_id).first()
        if not progress:
            progress = Progress(child_id=child_id, learning_content_id=story_id, total_num_questions=len(story.pages))
            self.db.session.add(progress)

        progress.completion_rate = (current_page / len(story.pages)) * 100

        self.db.session.commit()

        return progress, "Progress saved successfully"

    def complete_story(self, story_id, child_id):
        story = self.get_story(story_id)
        if not story:
            return None, "Story not found"

        progress = Progress.query.filter_by(child_id=child_id, learning_content_id=story_id).first()
        if not progress:
            progress = Progress(child_id=child_id, learning_content_id=story_id, total_num_questions=len(story.pages))
            self.db.session.add(progress)

        progress.completion_rate = 100
        progress.completed = True

        reward = Reward(child_id=child_id, story_id=story_id, content=f"Completed story: {story.title}")
        self.db.session.add(reward)

        self.db.session.commit()

        return reward, "Story completed and reward given"
    
    def submit_activity(self, activity_id, child_id, answers):
        activity = self.get_activity(activity_id)
        if not activity:
            return False, "Activity not found"

        total_questions = len(activity.questions)
        correct_answers = 0

        for question_id, answer in answers.items():
            question = next((q for q in activity.questions if q.id == int(question_id)), None)
            if question and question.correct_answer == answer:
                correct_answers += 1

        completion_rate = (correct_answers / total_questions) * 100

        progress = Progress.query.filter_by(child_id=child_id, learning_content_id=activity_id).first()
        if not progress:
            progress = Progress(child_id=child_id, learning_content_id=activity_id, total_questions=total_questions)
            self.db.session.add(progress)

        progress.completion_rate = completion_rate
        progress.completed = completion_rate == 100

        self.db.session.commit()

        return True, f"Activity submitted. You got {correct_answers} out of {total_questions} correct."
    
    def get_or_create_progress(self, story_id, child_id):
        progress = Progress.query.filter_by(learning_content_id=story_id, child_id=child_id).first()
        if not progress:
            progress = Progress(learning_content_id=story_id, child_id=child_id)
            db.session.add(progress)
            db.session.commit()
        return progress

    def update_progress(self, story_id, child_id, completion_rate):
        progress = self.get_or_create_progress(story_id, child_id)
        progress.completion_rate = completion_rate
        db.session.commit()

    def add_reward(self, story_id, child_id, content):
        reward = Reward(
            story_id=story_id,
            child_id=child_id,
            content=content
        )
        db.session.add(reward)
        db.session.commit()