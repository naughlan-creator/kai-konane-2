from models.page import Page
from config import db

class PageService:
    def __init__(self):
        self.db = db

    def add_page(self, page):
        self.db.session.add(page)
        self.db.session.commit()
        if self.get_page(page.id):
            return "Page added!!!"
        return "Page not added!!!"

    def get_page(self, page_id):
        return Page.query.get(page_id)

    def get_pages(self):
        return Page.query.all()

    def update_page(self, page):
        existing_page = self.get_page(page.id)
        if existing_page:
            existing_page.name = page.name
            self.db.session.commit()
            return "Page updated!!!"
        return "Page not updated!!!"

    def delete_page(self, page_id):
        page = self.get_page(page_id)
        if page:
            self.db.session.delete(page)
            self.db.session.commit()
            return "Page deleted!!!"
        return "Page not deleted!!!"