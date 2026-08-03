"""Schema cleanup: snake_case names, explicit ordering, indexes

* Renames "learningContent"/"learningPlan" to snake_case. The camelCase names
  are quoted, case-sensitive identifiers in Postgres, so any hand-written SQL
  had to quote them exactly or fail.
* Renames feedbacks.dateTime/isRead and rewards.dateAquired (a typo) to
  snake_case.
* Adds explicit ordering columns: question.position, answer.position and
  page.page_number. Order previously depended on primary key order, so editing
  a question moved it to the end of the activity.
* Adds a description to learning content, indexes the foreign keys, and makes
  the one-plan-per-child rule a database constraint.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b2c3d4e5f6a7'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    # --- table renames ----------------------------------------------------
    op.rename_table('learningContent', 'learning_content')
    op.rename_table('learningPlan', 'learning_plans')

    # --- learning content -------------------------------------------------
    with op.batch_alter_table('learning_content', schema=None) as batch_op:
        batch_op.add_column(sa.Column('description', sa.String(length=255), nullable=True))
        batch_op.alter_column('title', existing_type=sa.String(length=80),
                              type_=sa.String(length=120), existing_nullable=True)
        batch_op.create_index('ix_learning_content_type', ['type'])

    # --- explicit ordering ------------------------------------------------
    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position', sa.Integer(), nullable=False,
                                      server_default='0'))
        batch_op.alter_column('content', existing_type=sa.String(length=80),
                              type_=sa.String(length=255), existing_nullable=True)
        batch_op.create_index('ix_question_activity_id', ['activity_id'])

    with op.batch_alter_table('answer', schema=None) as batch_op:
        batch_op.add_column(sa.Column('position', sa.Integer(), nullable=False,
                                      server_default='0'))
        batch_op.alter_column('content', existing_type=sa.String(length=80),
                              type_=sa.String(length=255), existing_nullable=True)
        batch_op.create_index('ix_answer_question_id', ['question_id'])

    with op.batch_alter_table('page', schema=None) as batch_op:
        batch_op.add_column(sa.Column('page_number', sa.Integer(), nullable=False,
                                      server_default='1'))
        batch_op.alter_column('line_of_page', existing_type=sa.String(length=100),
                              type_=sa.String(length=500), existing_nullable=False)
        batch_op.create_index('ix_page_story_id', ['story_id'])

    # Seed the new ordering columns from the existing primary key order, which
    # is the order the rows were displayed in until now.
    op.execute("""
        UPDATE question SET position = (
            SELECT COUNT(*) FROM question AS earlier
            WHERE earlier.activity_id = question.activity_id
              AND earlier.id <= question.id
        )
    """)
    op.execute("""
        UPDATE answer SET position = (
            SELECT COUNT(*) FROM answer AS earlier
            WHERE earlier.question_id = answer.question_id
              AND earlier.id <= answer.id
        )
    """)
    op.execute("""
        UPDATE page SET page_number = (
            SELECT COUNT(*) FROM page AS earlier
            WHERE earlier.story_id = page.story_id
              AND earlier.id <= page.id
        )
    """)

    with op.batch_alter_table('page', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_page_story_number', ['story_id', 'page_number'])
        # is_last_page is now derived from page_number, so the stored flag can
        # no longer disagree with the actual position.
        batch_op.drop_column('is_last_page')

    # --- feedback ---------------------------------------------------------
    with op.batch_alter_table('feedbacks', schema=None) as batch_op:
        batch_op.alter_column('dateTime', new_column_name='sent_at',
                              existing_type=sa.DateTime(), existing_nullable=True)
        batch_op.alter_column('isRead', new_column_name='is_read',
                              existing_type=sa.Boolean(), existing_nullable=True)
        batch_op.alter_column('subject', existing_type=sa.String(length=50),
                              type_=sa.String(length=120), existing_nullable=False)
    op.execute("UPDATE feedbacks SET is_read = FALSE WHERE is_read IS NULL")
    with op.batch_alter_table('feedbacks', schema=None) as batch_op:
        batch_op.create_index('ix_feedbacks_sender_id', ['sender_id'])
        batch_op.create_index('ix_feedbacks_recipient_id', ['recipient_id'])
        batch_op.create_index('ix_feedbacks_child_id', ['child_id'])
        batch_op.create_index('ix_feedbacks_sent_at', ['sent_at'])

    # --- rewards ----------------------------------------------------------
    with op.batch_alter_table('rewards', schema=None) as batch_op:
        batch_op.alter_column('dateAquired', new_column_name='date_acquired',
                              existing_type=sa.Date(), existing_nullable=True)
        batch_op.create_index('ix_rewards_child_id', ['child_id'])
        batch_op.create_index('ix_rewards_activity_id', ['activity_id'])
        batch_op.create_index('ix_rewards_story_id', ['story_id'])

    # --- results ----------------------------------------------------------
    with op.batch_alter_table('results', schema=None) as batch_op:
        batch_op.create_index('ix_results_child_id', ['child_id'])
        batch_op.create_index('ix_results_activity_id', ['activity_id'])
        batch_op.create_index('ix_results_date_acquired', ['date_acquired'])

    # --- users ------------------------------------------------------------
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.create_index('ix_users_role', ['role'])
        batch_op.create_index('ix_users_type', ['type'])
    op.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")

    with op.batch_alter_table('children', schema=None) as batch_op:
        batch_op.alter_column('gender', existing_type=sa.String(length=10),
                              type_=sa.String(length=20), existing_nullable=False)
        batch_op.create_index('ix_children_parent_id', ['parent_id'])
        batch_op.create_index('ix_children_teacher_id', ['teacher_id'])
        batch_op.create_index('ix_children_preschool_id', ['preschool_id'])

    # --- one learning plan per child --------------------------------------
    op.execute("""
        DELETE FROM learning_plans
        WHERE id NOT IN (SELECT MIN(id) FROM learning_plans GROUP BY child_id)
    """)
    with op.batch_alter_table('learning_plans', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_learning_plan_child', ['child_id'])

    with op.batch_alter_table('preschools', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_preschool_name', ['name'])

    with op.batch_alter_table('activity', schema=None) as batch_op:
        batch_op.create_index('ix_activity_stem_code', ['stem_code'])
        batch_op.create_index('ix_activity_level', ['level'])

    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.create_index('ix_story_level', ['level'])


def downgrade():
    with op.batch_alter_table('story', schema=None) as batch_op:
        batch_op.drop_index('ix_story_level')

    with op.batch_alter_table('activity', schema=None) as batch_op:
        batch_op.drop_index('ix_activity_level')
        batch_op.drop_index('ix_activity_stem_code')

    with op.batch_alter_table('preschools', schema=None) as batch_op:
        batch_op.drop_constraint('uq_preschool_name', type_='unique')

    with op.batch_alter_table('learning_plans', schema=None) as batch_op:
        batch_op.drop_constraint('uq_learning_plan_child', type_='unique')

    with op.batch_alter_table('children', schema=None) as batch_op:
        batch_op.drop_index('ix_children_preschool_id')
        batch_op.drop_index('ix_children_teacher_id')
        batch_op.drop_index('ix_children_parent_id')
        batch_op.alter_column('gender', existing_type=sa.String(length=20),
                              type_=sa.String(length=10), existing_nullable=False)

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('ix_users_type')
        batch_op.drop_index('ix_users_role')
        batch_op.drop_column('created_at')

    with op.batch_alter_table('results', schema=None) as batch_op:
        batch_op.drop_index('ix_results_date_acquired')
        batch_op.drop_index('ix_results_activity_id')
        batch_op.drop_index('ix_results_child_id')

    with op.batch_alter_table('rewards', schema=None) as batch_op:
        batch_op.drop_index('ix_rewards_story_id')
        batch_op.drop_index('ix_rewards_activity_id')
        batch_op.drop_index('ix_rewards_child_id')
        batch_op.alter_column('date_acquired', new_column_name='dateAquired',
                              existing_type=sa.Date(), existing_nullable=True)

    with op.batch_alter_table('feedbacks', schema=None) as batch_op:
        batch_op.drop_index('ix_feedbacks_sent_at')
        batch_op.drop_index('ix_feedbacks_child_id')
        batch_op.drop_index('ix_feedbacks_recipient_id')
        batch_op.drop_index('ix_feedbacks_sender_id')
        batch_op.alter_column('subject', existing_type=sa.String(length=120),
                              type_=sa.String(length=50), existing_nullable=False)
        batch_op.alter_column('is_read', new_column_name='isRead',
                              existing_type=sa.Boolean(), existing_nullable=True)
        batch_op.alter_column('sent_at', new_column_name='dateTime',
                              existing_type=sa.DateTime(), existing_nullable=True)

    with op.batch_alter_table('page', schema=None) as batch_op:
        batch_op.add_column(sa.Column('is_last_page', sa.Boolean(), nullable=False,
                                      server_default=sa.false()))
        batch_op.drop_constraint('uq_page_story_number', type_='unique')
        batch_op.drop_index('ix_page_story_id')
        batch_op.alter_column('line_of_page', existing_type=sa.String(length=500),
                              type_=sa.String(length=100), existing_nullable=False)
        batch_op.drop_column('page_number')

    with op.batch_alter_table('answer', schema=None) as batch_op:
        batch_op.drop_index('ix_answer_question_id')
        batch_op.alter_column('content', existing_type=sa.String(length=255),
                              type_=sa.String(length=80), existing_nullable=True)
        batch_op.drop_column('position')

    with op.batch_alter_table('question', schema=None) as batch_op:
        batch_op.drop_index('ix_question_activity_id')
        batch_op.alter_column('content', existing_type=sa.String(length=255),
                              type_=sa.String(length=80), existing_nullable=True)
        batch_op.drop_column('position')

    with op.batch_alter_table('learning_content', schema=None) as batch_op:
        batch_op.drop_index('ix_learning_content_type')
        batch_op.alter_column('title', existing_type=sa.String(length=120),
                              type_=sa.String(length=80), existing_nullable=True)
        batch_op.drop_column('description')

    op.rename_table('learning_plans', 'learningPlan')
    op.rename_table('learning_content', 'learningContent')
