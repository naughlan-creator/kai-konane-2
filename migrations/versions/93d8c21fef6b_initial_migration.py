"""Initial migration

Revision ID: 93d8c21fef6b
Revises: 
Create Date: 2024-10-19 19:08:30.682703

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '93d8c21fef6b'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('learningContent',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('title', sa.String(length=80), nullable=True),
    sa.Column('type', sa.Enum('ACTIVITY', 'STORY', 'GAME', name='type'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('preschools',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('username', sa.String(length=80), nullable=False),
    sa.Column('password', sa.String(length=255), nullable=False),
    sa.Column('email', sa.String(length=120), nullable=False),
    sa.Column('role', sa.Enum('ADMIN', 'CHILD', 'PARENT', 'TEACHER', name='role'), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email'),
    sa.UniqueConstraint('username')
    )
    op.create_table('activity',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('stem_code', sa.Enum('SCIENCE', 'TECHNOLOGY', 'ENGINEERING', 'MATH', name='stem_code'), nullable=True),
    sa.Column('level', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='level'), nullable=False),
    sa.Column('cover_image', sa.String(length=255), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['learningContent.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('admin',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('name', sa.String(length=5), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('parents',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('firstname', sa.String(length=100), nullable=True),
    sa.Column('lastname', sa.String(length=100), nullable=True),
    sa.Column('education_level', sa.Enum('SOME_HIGH_SCHOOL', 'HIGH_SCHOOL', 'SOME_COLLEGE', 'ASSOCIATES_DEGREE', 'BACHELORS_DEGREE', 'MASTERS_DEGREE', name='education_level'), nullable=False),
    sa.ForeignKeyConstraint(['id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('story',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('cover_page', sa.String(length=255), nullable=True),
    sa.Column('level', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='level'), nullable=False),
    sa.ForeignKeyConstraint(['id'], ['learningContent.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('teachers',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('firstname', sa.String(length=100), nullable=True),
    sa.Column('lastname', sa.String(length=100), nullable=True),
    sa.Column('preschool_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['preschool_id'], ['preschools.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('children',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('firstname', sa.String(length=100), nullable=False),
    sa.Column('lastname', sa.String(length=100), nullable=False),
    sa.Column('age', sa.Integer(), nullable=False),
    sa.Column('gender', sa.String(length=10), nullable=False),
    sa.Column('parent_id', sa.Integer(), nullable=False),
    sa.Column('teacher_id', sa.Integer(), nullable=True),
    sa.Column('preschool_id', sa.Integer(), nullable=True),
    sa.Column('race_ethnicity', sa.String(length=50), nullable=True),
    sa.Column('lunch_type', sa.Enum('STANDARD', 'FREE_REDUCED', name='lunch_type'), nullable=False),
    sa.Column('parent_education', sa.Enum('SOME_HIGH_SCHOOL', 'HIGH_SCHOOL', 'SOME_COLLEGE', 'ASSOCIATES_DEGREE', 'BACHELORS_DEGREE', 'MASTERS_DEGREE', name='parent_education'), nullable=False),
    sa.Column('recommended_level', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='recommended_level'), nullable=True),
    sa.ForeignKeyConstraint(['id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['parent_id'], ['parents.id'], ),
    sa.ForeignKeyConstraint(['preschool_id'], ['preschools.id'], ),
    sa.ForeignKeyConstraint(['teacher_id'], ['teachers.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('page',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('line_of_page', sa.String(length=100), nullable=False),
    sa.Column('image_filename', sa.String(length=255), nullable=True),
    sa.Column('is_last_page', sa.Boolean(), nullable=False),
    sa.Column('story_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['story_id'], ['story.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('question',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('content', sa.String(length=80), nullable=True),
    sa.Column('activity_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['activity_id'], ['activity.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('answer',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('content', sa.String(length=80), nullable=True),
    sa.Column('is_correct', sa.Boolean(), nullable=True),
    sa.Column('question_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['question_id'], ['question.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('feedbacks',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('sender_id', sa.Integer(), nullable=False),
    sa.Column('recipient_id', sa.Integer(), nullable=False),
    sa.Column('subject', sa.String(length=50), nullable=False),
    sa.Column('message', sa.Text(length=255), nullable=False),
    sa.Column('dateTime', sa.DateTime(), nullable=True),
    sa.Column('isRead', sa.Boolean(), nullable=True),
    sa.Column('child_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['child_id'], ['children.id'], ),
    sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['sender_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('learningPlan',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('child_id', sa.Integer(), nullable=True),
    sa.Column('science_level', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='science_level'), nullable=True),
    sa.Column('technology_level', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='technology_level'), nullable=True),
    sa.Column('engineering_level', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='engineering_level'), nullable=True),
    sa.Column('math_level', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='math_level'), nullable=True),
    sa.Column('story_level', sa.Enum('BEGINNER', 'INTERMEDIATE', 'ADVANCED', name='story_level'), nullable=True),
    sa.ForeignKeyConstraint(['child_id'], ['children.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('progress',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('completion_rate', sa.Float(), nullable=True),
    sa.Column('child_id', sa.Integer(), nullable=False),
    sa.Column('learning_content_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['child_id'], ['children.id'], ),
    sa.ForeignKeyConstraint(['learning_content_id'], ['learningContent.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('results',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('child_id', sa.Integer(), nullable=False),
    sa.Column('activity_id', sa.Integer(), nullable=False),
    sa.Column('score', sa.Float(), nullable=True),
    sa.Column('date_acquired', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['activity_id'], ['activity.id'], ),
    sa.ForeignKeyConstraint(['child_id'], ['children.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('rewards',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('activity_id', sa.Integer(), nullable=True),
    sa.Column('story_id', sa.Integer(), nullable=True),
    sa.Column('child_id', sa.Integer(), nullable=False),
    sa.Column('content', sa.String(length=255), nullable=True),
    sa.Column('dateAquired', sa.Date(), nullable=True),
    sa.ForeignKeyConstraint(['activity_id'], ['activity.id'], ),
    sa.ForeignKeyConstraint(['child_id'], ['children.id'], ),
    sa.ForeignKeyConstraint(['story_id'], ['story.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('rewards')
    op.drop_table('results')
    op.drop_table('progress')
    op.drop_table('learningPlan')
    op.drop_table('feedbacks')
    op.drop_table('answer')
    op.drop_table('question')
    op.drop_table('page')
    op.drop_table('children')
    op.drop_table('teachers')
    op.drop_table('story')
    op.drop_table('parents')
    op.drop_table('admin')
    op.drop_table('activity')
    op.drop_table('users')
    op.drop_table('preschools')
    op.drop_table('learningContent')
    # ### end Alembic commands ###