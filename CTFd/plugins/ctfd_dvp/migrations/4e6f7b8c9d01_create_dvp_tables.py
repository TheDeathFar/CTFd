"""
Create DVP tables (ArgoCD Edition)

Revision ID: 4e6f7b8c9d01
Revises: 
Create Date: 2026-04-17
Updated:   2026-04-28
"""

from alembic import op
import sqlalchemy as sa


revision = '4e6f7b8c9d01'
down_revision = None
branch_labels = ('ctfd_dvp',)
depends_on = None


def upgrade(op=None):
    """Создание таблиц"""
    
    # Таблица для расширенных настроек челленджей
    op.create_table(
        'dvp_challenges',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('git_repo_url', sa.String(512), nullable=False, server_default=''),
        sa.Column('git_ref', sa.String(64), nullable=True, server_default='main'),
        sa.Column('chart_path', sa.String(256), nullable=True, server_default='.'),
        sa.Column('helm_values', sa.Text(), nullable=True, server_default='{}'),
        sa.Column('timeout', sa.Integer(), nullable=True, server_default='3600'),
        sa.Column('subdomain_template', sa.String(128), nullable=True, server_default=''),
        sa.Column('check_script', sa.Text(), nullable=True),
        sa.Column('auto_submit_flag', sa.Boolean(), nullable=True, server_default=sa.false()),
        sa.ForeignKeyConstraint(['id'], ['challenges.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Таблица для активных окружений
    op.create_table(
        'dvp_environments',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('challenge_id', sa.Integer(), nullable=False),
        sa.Column('project_name', sa.String(128), nullable=False),
        sa.Column('subdomain', sa.String(256), nullable=True),
        sa.Column('check_status', sa.String(32), nullable=True, server_default='pending'),
        sa.Column('status', sa.String(32), nullable=True, server_default='active'),
        sa.Column('created_at', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Индексы для быстрого поиска
    op.create_index('idx_dvp_env_user_challenge', 'dvp_environments', ['user_id', 'challenge_id'])
    op.create_index('idx_dvp_env_expires', 'dvp_environments', ['expires_at'])


def downgrade(op=None):
    """Удаление таблиц (откат миграции)"""
    op.drop_index('idx_dvp_env_expires', table_name='dvp_environments')
    op.drop_index('idx_dvp_env_user_challenge', table_name='dvp_environments')
    op.drop_table('dvp_environments')
    op.drop_table('dvp_challenges')