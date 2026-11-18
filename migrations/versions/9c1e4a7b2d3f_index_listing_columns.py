"""Index pastes.created_at and attachments.paste_id

Revision ID: 9c1e4a7b2d3f
Revises: 273bba5a4815
Create Date: 2026-11-17 19:00:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = '9c1e4a7b2d3f'
down_revision = '273bba5a4815'
branch_labels = None
depends_on = None


def upgrade():
    op.create_index('ix_pastes_created_at', 'pastes', ['created_at'])
    op.create_index('ix_attachments_paste_id', 'attachments', ['paste_id'])


def downgrade():
    op.drop_index('ix_attachments_paste_id', table_name='attachments')
    op.drop_index('ix_pastes_created_at', table_name='pastes')
