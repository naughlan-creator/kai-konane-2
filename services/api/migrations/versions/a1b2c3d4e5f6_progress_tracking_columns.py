"""Add progress tracking columns and widen admin.name

The service layer already passed ``total_num_questions`` to Progress and set
``progress.completed``, but neither column existed: the constructor raised a
TypeError and the completion flag was only ever an in-memory attribute.

Revision ID: a1b2c3d4e5f6
Revises: fe01c243a712
Create Date: 2026-08-02

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a1b2c3d4e5f6'
down_revision = 'fe01c243a712'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('progress', schema=None) as batch_op:
        batch_op.add_column(sa.Column('total_num_questions', sa.Integer(),
                                      nullable=True, server_default='0'))
        batch_op.add_column(sa.Column('completed', sa.Boolean(),
                                      nullable=False, server_default=sa.false()))

    # Anything already at 100% counts as completed.
    op.execute("UPDATE progress SET completed = TRUE WHERE completion_rate >= 100")

    # One progress row per (child, content). Drop any duplicates the old code
    # could create before adding the constraint.
    op.execute("""
        DELETE FROM progress
        WHERE id NOT IN (
            SELECT keep_id FROM (
                SELECT MAX(id) AS keep_id
                FROM progress
                GROUP BY child_id, learning_content_id
            ) AS keepers
        )
    """)

    with op.batch_alter_table('progress', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_progress_child_content',
                                          ['child_id', 'learning_content_id'])

    with op.batch_alter_table('admin', schema=None) as batch_op:
        batch_op.alter_column('name',
                              existing_type=sa.String(length=5),
                              type_=sa.String(length=100),
                              existing_nullable=True)


def downgrade():
    with op.batch_alter_table('admin', schema=None) as batch_op:
        batch_op.alter_column('name',
                              existing_type=sa.String(length=100),
                              type_=sa.String(length=5),
                              existing_nullable=True)

    with op.batch_alter_table('progress', schema=None) as batch_op:
        batch_op.drop_constraint('uq_progress_child_content', type_='unique')
        batch_op.drop_column('completed')
        batch_op.drop_column('total_num_questions')
