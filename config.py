import os
from flask import Flask
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = os.getenv('JAWSDB_URL', 'postgresql://kai_konane_user:Yixi8qRycyKnKKZ17uOqBL5Nzx0zZ2Ft@dpg-csbrcl5ds78s73be6bk0-a.oregon-postgres.render.com/kai_konane')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', '1234')

db = SQLAlchemy(app)

migrate = Migrate(app, db)