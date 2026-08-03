from models.story import Story
from models.child import Level
from models.progress import Progress
from models.reward import Reward
from models.page import Page
from services.media import resolve_image
from config import db as default_db


class StoryError(ValueError):
    """Raised when submitted story content is not usable."""


class StoryService:
    def __init__(self, db=None):
        self.db = db or default_db

    # ---------------------------------------------------------------- authoring

    @staticmethod
    def _validate(title, level, pages_data):
        if not (title or '').strip():
            raise StoryError("A story needs a title")

        story_level = Level.coerce(level)
        if story_level is None:
            raise StoryError("Choose a valid level")

        cleaned = []
        for index, page_data in enumerate(pages_data or [], start=1):
            line = (page_data.get('line_of_page') or '').strip()
            if not line:
                raise StoryError(f"Page {index} is missing its text")
            cleaned.append({
                'id': page_data.get('id'),
                'line_of_page': line,
                'image': page_data.get('image'),
                'existing_image': page_data.get('existing_image'),
            })

        if not cleaned:
            raise StoryError("A story needs at least one page")

        return story_level, cleaned

    def add_story(self, title, level, cover_image, pages, description=None,
                  existing_cover=None):
        try:
            story_level, pages_data = self._validate(title, level, pages)
        except StoryError as e:
            return None, str(e)

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
            return story, "Story added!!!"
        except Exception as e:
            self.db.session.rollback()
            return None, f"Story not added!!! Error: {e}"

    def update_story(self, story_id, title=None, level=None, cover_image=None,
                     pages=None, description=None, existing_cover=None):
        story = self.get_story(story_id)
        if not story:
            return "Story not found!!!"

        try:
            story_level, pages_data = self._validate(
                title or story.title, level or story.level, pages)
        except StoryError as e:
            return f"Story not updated!!! {e}"

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
            return "Story updated!!!"
        except Exception as e:
            self.db.session.rollback()
            return f"Story not updated!!! Error: {e}"

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
        if not story:
            return "Story not found!!!"

        self.db.session.delete(story)
        self.db.session.commit()
        return "Story deleted!!!"

    def add_page(self, story_id, line_of_page):
        story = self.get_story(story_id)
        if not story:
            return "Story not found!!!"
        next_number = max((page.page_number for page in story.pages), default=0) + 1
        page = Page(line_of_page=line_of_page, page_number=next_number)
        story.pages.append(page)
        self.db.session.commit()
        return page

    # ------------------------------------------------------------------ reading

    def get_story(self, story_id):
        return self.db.session.get(Story, story_id)

    def get_stories(self):
        return Story.query.order_by(Story.id).all()

    def get_stories_for_level(self, level):
        allowed = [candidate for candidate in Level if candidate.rank <= level.rank]
        return (Story.query
                .filter(Story.level.in_(allowed))
                .order_by(Story.level, Story.id)
                .all())

    # ------------------------------------------------------------ reading a story

    def get_story_progress(self, story_id, child_id):
        progress = Progress.query.filter_by(child_id=child_id,
                                            learning_content_id=story_id).first()
        return progress.completion_rate if progress else 0

    def get_or_create_progress(self, story_id, child_id):
        progress = Progress.query.filter_by(learning_content_id=story_id,
                                            child_id=child_id).first()
        if not progress:
            progress = Progress(learning_content_id=story_id, child_id=child_id)
            self.db.session.add(progress)
            self.db.session.commit()
        return progress

    def update_progress(self, story_id, child_id, completion_rate):
        progress = self.get_or_create_progress(story_id, child_id)
        progress.update_completion_rate(completion_rate)
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

    def add_reward(self, story_id, child_id, content):
        reward = Reward(child_id=child_id, story_id=story_id, content=content)
        self.db.session.add(reward)
        self.db.session.commit()
        return reward


def _as_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
