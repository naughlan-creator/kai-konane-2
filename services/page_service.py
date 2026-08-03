from models.page import Page
from config import db as default_db

class PageService:
    def __init__(self, db=None):
        self.db = db or default_db

    def add_page(self, page):
        self.db.session.add(page)
        self.db.session.commit()
        if self.get_page(page.id):
            return "Page added!!!"
        return "Page not added!!!"

    def get_page(self, page_id):
        return self.db.session.get(Page, page_id)

    def get_pages(self):
        return Page.query.all()

    def update_page(self, page_id, line_of_page=None, image_filename=None, page_number=None):
        existing_page = self.get_page(page_id)
        if not existing_page:
            return "Page not updated!!!"
        if line_of_page is not None:
            existing_page.line_of_page = line_of_page
        if image_filename is not None:
            existing_page.image_filename = image_filename
        if page_number is not None:
            # is_last_page is derived from position now, so there is no separate
            # flag to keep in step.
            existing_page.page_number = int(page_number)
        self.db.session.commit()
        return "Page updated!!!"

    def delete_page(self, page_id):
        page = self.get_page(page_id)
        if page:
            self.db.session.delete(page)
            self.db.session.commit()
            return "Page deleted!!!"
        return "Page not deleted!!!"
