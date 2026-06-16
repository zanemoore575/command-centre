"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-01-15

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create journal_entries table
    op.create_table(
        'journal_entries',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('entry_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('entry_type', sa.String(length=50), nullable=True),
        sa.Column('mood', sa.String(length=50), nullable=True),
        sa.Column('energy_level', sa.Integer(), nullable=True),
        sa.Column('is_processed', sa.Boolean(), nullable=True),
        sa.Column('extra_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_journal_entries_entry_date'), 'journal_entries', ['entry_date'], unique=False)
    op.create_index(op.f('ix_journal_entries_id'), 'journal_entries', ['id'], unique=False)
    op.create_index(op.f('ix_journal_entries_is_processed'), 'journal_entries', ['is_processed'], unique=False)

    # Create people table
    op.create_table(
        'people',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('company', sa.String(length=255), nullable=True),
        sa.Column('role', sa.String(length=255), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('first_mentioned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_mentioned_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('mention_count', sa.Integer(), nullable=True),
        sa.Column('relationship_status', sa.String(length=50), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.Column('extra_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_people_id'), 'people', ['id'], unique=False)
    op.create_index(op.f('ix_people_name'), 'people', ['name'], unique=False)

    # Create commitments table
    op.create_table(
        'commitments',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('journal_entry_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('due_date', sa.Date(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('priority', sa.String(length=50), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['people.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_commitments_due_date'), 'commitments', ['due_date'], unique=False)
    op.create_index(op.f('ix_commitments_id'), 'commitments', ['id'], unique=False)
    op.create_index(op.f('ix_commitments_status'), 'commitments', ['status'], unique=False)

    # Create pain_points table
    op.create_table(
        'pain_points',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('journal_entry_id', sa.Integer(), nullable=False),
        sa.Column('person_id', sa.Integer(), nullable=True),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('severity', sa.String(length=50), nullable=True),
        sa.Column('frequency_mentioned', sa.Integer(), nullable=True),
        sa.Column('first_mentioned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('last_mentioned_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('validation_status', sa.String(length=50), nullable=True),
        sa.Column('extra_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['person_id'], ['people.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_pain_points_category'), 'pain_points', ['category'], unique=False)
    op.create_index(op.f('ix_pain_points_id'), 'pain_points', ['id'], unique=False)

    # Create entity_mentions table
    op.create_table(
        'entity_mentions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('journal_entry_id', sa.Integer(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.Integer(), nullable=True),
        sa.Column('context_snippet', sa.Text(), nullable=True),
        sa.Column('sentiment', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['journal_entry_id'], ['journal_entries.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_entity_mentions_entity_type'), 'entity_mentions', ['entity_type'], unique=False)
    op.create_index(op.f('ix_entity_mentions_id'), 'entity_mentions', ['id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_entity_mentions_id'), table_name='entity_mentions')
    op.drop_index(op.f('ix_entity_mentions_entity_type'), table_name='entity_mentions')
    op.drop_table('entity_mentions')

    op.drop_index(op.f('ix_pain_points_id'), table_name='pain_points')
    op.drop_index(op.f('ix_pain_points_category'), table_name='pain_points')
    op.drop_table('pain_points')

    op.drop_index(op.f('ix_commitments_status'), table_name='commitments')
    op.drop_index(op.f('ix_commitments_id'), table_name='commitments')
    op.drop_index(op.f('ix_commitments_due_date'), table_name='commitments')
    op.drop_table('commitments')

    op.drop_index(op.f('ix_people_name'), table_name='people')
    op.drop_index(op.f('ix_people_id'), table_name='people')
    op.drop_table('people')

    op.drop_index(op.f('ix_journal_entries_is_processed'), table_name='journal_entries')
    op.drop_index(op.f('ix_journal_entries_id'), table_name='journal_entries')
    op.drop_index(op.f('ix_journal_entries_entry_date'), table_name='journal_entries')
    op.drop_table('journal_entries')
