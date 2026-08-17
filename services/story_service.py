from config import db as default_db
from models.child import Level
from models.page import Page
from models.progress import Progress
from models.reward import Reward
from models.story import Story
from services.errors import NotFound, ValidationError
from services.media import resolve_image


class StoryService:
    def __init__(self, db=None):
        self.db = db or default_db

    # ---------------------------------------------------------------- authoring

    @staticmethod
    def _validate(title, level, pages_data):
        if not (title or '').strip():
            raise ValidationError("A story needs a title")

        story_level = Level.coerce(level)
        if story_level is None:
            raise ValidationError("Choose a valid level")

        cleaned = []
        for index, page_data in enumerate(pages_data or [], start=1):
            line = (page_data.get('line_of_page') or '').strip()
            if not line:
                raise ValidationError(f"Page {index} is missing its text")
            cleaned.append({
                'id': page_data.get('id'),
                'line_of_page': line,
                'image': page_data.get('image'),
                'existing_image': page_data.get('existing_image'),
            })

        if not cleaned:
            raise ValidationError("A story needs at least one page")

        return story_level, cleaned

    def add_story(self, title, level, cover_image, pages, description=None,
                  existing_cover=None):
        story_level, pages_data = self._validate(title, level, pages)

        try:
            story = Story(
                title=title.strip(),
                description=(description or '').strip() or None,
                level=story_level,
                cover_page=resolve_image(cover_image, existing_cover),
            )

            for number, page_data in enumerate(pages_data, start=1):
                story.pages.append(Page(
                    line_of_page=page_data['line_of_page'],
                    image_filename=resolve_image(page_data['image'],
                                                 page_data['existing_image']),
                    page_number=number,
                ))

            self.db.session.add(story)
            self.db.session.commit()
            return story
        except Exception:
            self.db.session.rollback()
            raise

    def update_story(self, story_id, title=None, level=None, cover_image=None,
                     pages=None, description=None, existing_cover=None):
        story = self.get_story(story_id)
        if story is None:
            raise NotFound("That story no longer exists")

        story_level, pages_data = self._validate(
            title or story.title, level or story.level, pages)

        try:
            story.title = (title or story.title).strip()
            if description is not None:
                story.description = description.strip() or None
            story.level = story_level
            # The column is cover_page; the old code assigned to `cover_image`,
            # which just set a throwaway attribute and lost the new cover.
            story.cover_page = resolve_image(cover_image, existing_cover, story.cover_page)

            self._sync_pages(story, pages_data)

            # The old version never committed, so story edits were discarded.
            self.db.session.commit()
            return story
        except Exception:
            self.db.session.rollback()
            raise

    def _sync_pages(self, story, pages_data):
        """Match stored pages to submitted pages, keeping images when untouched."""
        existing = {page.id: page for page in story.pages}
        # Track submission order explicitly. story.pages is ordered by
        # page_number, so it still reflects the *old* order while we work.
        ordered = []

        for page_data in pages_data:
            page = existing.get(_as_int(page_data.get('id')))
            if page is None:
                page = Page(
                    line_of_page=page_data['line_of_page'],
                    image_filename=resolve_image(page_data['image'],
                                                 page_data['existing_image']),
                )
                story.pages.append(page)
            else:
                page.line_of_page = page_data['line_of_page']
                page.image_filename = resolve_image(page_data['image'],
                                                    page_data['existing_image'],
                                                    page.image_filename)
            ordered.append(page)

        keep = {id(page) for page in ordered}
        for page in list(story.pages):
            if id(page) not in keep:
                story.pages.remove(page)

        # (story_id, page_number) is unique, so park every page on a number that
        # cannot collide before assigning the final ones.
        for offset, page in enumerate(ordered, start=1):
            page.page_number = offset + 10000
        self.db.session.flush()
        for number, page in enumerate(ordered, start=1):
            page.page_number = number
        self.db.session.flush()

    def delete_story(self, story_id):
        story = self.get_story(story_id)
        if story is None:
            raise NotFound("That story no longer exists")

        self.db.session.delete(story)
        self.db.session.commit()
        return story


    def get_story(self, story_id):
        return self.db.session.get(Story, story_id)

    def get_stories(self):
        return Story.query.order_by(Story.id).all()



    def get_or_create_progress(self, story_id, child_id):
        progress = Progress.query.filter_by(learning_content_id=story_id,
                                            child_id=child_id).first()
        if not progress:
            progress = Progress(learning_content_id=story_id, child_id=child_id)
            self.db.session.add(progress)
            self.db.session.commit()
        return progress


    def save_story_progress(self, story_id, child_id, current_page):
        story = self.get_story(story_id)
        if not story:
            return None, "Story not found"

        progress = self.get_or_create_progress(story_id, child_id)
        total_pages = len(story.pages)
        progress.total_num_questions = total_pages

        if total_pages:
            progress.update_completion_rate((current_page / total_pages) * 100)
        else:
            progress.completion_rate = 0

        self.db.session.commit()
        return progress, "Progress saved successfully"

    def complete_story(self, story_id, child_id):
        story = self.get_story(story_id)
        if not story:
            return None, "Story not found"

        progress = self.get_or_create_progress(story_id, child_id)
        progress.total_num_questions = len(story.pages)
        progress.mark_as_completed()

        content = f"Completed story: {story.title}"
        reward = Reward.query.filter_by(child_id=child_id, story_id=story_id,
                                        content=content).first()
        if reward is None:
            # Without this check, re-reading a story hands out the same badge again.
            reward = Reward(child_id=child_id, story_id=story_id, content=content)
            self.db.session.add(reward)

        self.db.session.commit()
        return reward, "Story completed and reward given"


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
