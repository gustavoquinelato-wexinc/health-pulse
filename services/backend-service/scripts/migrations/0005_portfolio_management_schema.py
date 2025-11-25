#!/usr/bin/env python3
"""
Migration 0005: Portfolio Management Schema
Description: Creates comprehensive agile portfolio management schema including sprints, programs, portfolios, risks, dependencies, and OKRs
Author: Pulse Platform Team
Date: 2025-11-18

This migration creates:
- Sprints table with Jira sprint report metrics
- Programs table for quarterly planning (generic, not SAFe PI)
- Portfolios table for annual/strategic planning
- Work Item Sprints junction table for sprint assignments
- Risks table with probability/impact assessment
- Dependencies table with cross-team tracking
- Objectives and Key Results tables for OKR framework
- Junction tables for polymorphic relationships
"""

import os
import sys
import argparse
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime

# Add the backend service to the path to access database configuration
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

def get_database_connection():
    """Get database connection using backend service configuration."""
    try:
        from app.core.config import Settings
        config = Settings()

        connection = psycopg2.connect(
            host=config.POSTGRES_HOST,
            port=config.POSTGRES_PORT,
            database=config.POSTGRES_DATABASE,
            user=config.POSTGRES_USER,
            password=config.POSTGRES_PASSWORD
        )
        return connection
    except Exception as e:
        print(f"❌ Error connecting to database: {e}")
        raise

def apply(connection):
    """Apply the portfolio management schema migration."""
    print("📋 Starting Migration 0005: Portfolio Management Schema")
    print("=" * 80)

    cursor = connection.cursor()

    # ============================================================================
    # PORTFOLIOS TABLE (Strategic Level - Annual Planning)
    # ============================================================================
    print("\n📊 Creating portfolios table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS portfolios (
            id SERIAL PRIMARY KEY,
            
            -- Identifiers (NO external_id - manually created)
            name VARCHAR(255) NOT NULL,
            description TEXT,
            
            -- Portfolio Details
            state VARCHAR(50),                 -- active, archived, planning
            portfolio_type VARCHAR(50),        -- annual, strategic, innovation
            
            -- Dates
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            
            -- Strategic Alignment
            strategic_theme TEXT,
            business_owner VARCHAR(255),
            
            -- Financial (optional)
            budget_allocated DECIMAL(15,2),
            budget_spent DECIMAL(15,2),
            
            -- Health Metrics
            health_score FLOAT,
            risk_score FLOAT,
            
            -- IntegrationBaseEntity fields (tenant-level only, no integration)
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_updated_at TIMESTAMP DEFAULT NOW(),
            
            CONSTRAINT uk_portfolios_name UNIQUE(tenant_id, name)
        );
    """)
    print("✅ Portfolios table created")

    # ============================================================================
    # PROGRAMS TABLE (Tactical Level - Quarterly Planning)
    # ============================================================================
    print("\n📊 Creating programs table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS programs (
            id SERIAL PRIMARY KEY,
            
            -- Identifiers (NO external_id - manually created)
            name VARCHAR(255) NOT NULL,
            description TEXT,
            
            -- Program Details
            state VARCHAR(50),                 -- planning, active, completed, archived
            program_type VARCHAR(50),          -- quarterly, release_train, custom
            
            -- Dates
            start_date TIMESTAMP NOT NULL,
            end_date TIMESTAMP NOT NULL,
            
            -- Hierarchy
            portfolio_id INTEGER REFERENCES portfolios(id),
            
            -- Planning
            planning_objectives TEXT,
            
            -- Metrics (aggregated from sprints)
            planned_capacity FLOAT,
            delivered_capacity FLOAT,
            predictability_percentage FLOAT,
            
            -- Team/Resource
            team_count INTEGER,
            
            -- IntegrationBaseEntity fields (tenant-level only, no integration)
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_updated_at TIMESTAMP DEFAULT NOW(),
            
            CONSTRAINT uk_programs_name UNIQUE(tenant_id, name)
        );
    """)
    print("✅ Programs table created")

    # ============================================================================
    # SPRINTS TABLE (Operational Level - Sprint Execution)
    # ============================================================================
    print("\n📊 Creating sprints table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sprints (
            id SERIAL PRIMARY KEY,

            -- Identifiers
            external_id VARCHAR(50) NOT NULL,
            name VARCHAR(255) NOT NULL,
            sequence INTEGER,

            -- Sprint Details
            state VARCHAR(50) NOT NULL,       -- ACTIVE, CLOSED, FUTURE
            goal TEXT,

            -- Dates
            start_date TIMESTAMP,
            end_date TIMESTAMP,
            complete_date TIMESTAMP,

            -- Jira-specific
            board_id INTEGER,
            sprint_version INTEGER,

            -- Hierarchy
            program_id INTEGER REFERENCES programs(id),

            -- Sprint Report Metrics (from Jira API)
            completed_estimate FLOAT,
            not_completed_estimate FLOAT,
            punted_estimate FLOAT,
            total_estimate FLOAT,

            -- Calculated metrics
            completion_percentage FLOAT,
            velocity FLOAT,

            -- Sprint health indicators
            scope_change_count INTEGER,
            carry_over_count INTEGER,

            -- IntegrationBaseEntity fields
            integration_id INTEGER NOT NULL REFERENCES integrations(id),
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_updated_at TIMESTAMP DEFAULT NOW(),

            CONSTRAINT uk_sprints_external_id UNIQUE(tenant_id, integration_id, external_id)
        );
    """)
    print("✅ Sprints table created")

    # ============================================================================
    # WORK_ITEMS_SPRINTS TABLE (Junction - Sprint Assignments)
    # ============================================================================
    print("\n📊 Creating work_items_sprints junction table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS work_items_sprints (
            id SERIAL PRIMARY KEY,

            -- Relationships
            work_item_id INTEGER NOT NULL REFERENCES work_items(id),
            sprint_id INTEGER NOT NULL REFERENCES sprints(id),

            -- Sprint Assignment History
            added_date TIMESTAMP NOT NULL,
            removed_date TIMESTAMP,

            -- Sprint Report Classification
            sprint_outcome VARCHAR(50),       -- completed, not_completed, punted, completed_another_sprint
            added_during_sprint BOOLEAN DEFAULT FALSE,

            -- Commitment tracking
            committed BOOLEAN DEFAULT FALSE,

            -- Estimate snapshots
            estimate_at_start FLOAT,
            estimate_at_end FLOAT,

            -- Carry-over tracking
            carried_over_from_sprint_id INTEGER REFERENCES sprints(id),
            carried_over_to_sprint_id INTEGER REFERENCES sprints(id),

            -- IntegrationBaseEntity fields (simplified)
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_updated_at TIMESTAMP DEFAULT NOW(),

            CONSTRAINT uk_work_item_sprint UNIQUE(work_item_id, sprint_id, added_date)
        );
    """)
    print("✅ Work items sprints junction table created")

    # ============================================================================
    # RISKS TABLE (Risk Management)
    # ============================================================================
    print("\n📊 Creating risks table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risks (
            id SERIAL PRIMARY KEY,

            -- Identifiers (NO external_id - manually created)
            title VARCHAR(500) NOT NULL,
            description TEXT,

            -- Risk Classification
            risk_type VARCHAR(50),            -- technical, schedule, resource, budget, compliance, security, market
            category VARCHAR(50),             -- threat, opportunity

            -- Risk Assessment
            probability VARCHAR(50),          -- very_low, low, medium, high, very_high
            impact VARCHAR(50),               -- very_low, low, medium, high, very_high
            risk_score FLOAT,                 -- Calculated: probability × impact

            -- Risk Status
            state VARCHAR(50),                -- identified, analyzing, mitigating, monitoring, closed
            mitigation_plan TEXT,

            -- Ownership
            owner VARCHAR(255),

            -- Dates
            target_resolution_date TIMESTAMP,
            critical_resolution_date TIMESTAMP,
            actual_resolution_date TIMESTAMP,

            -- IntegrationBaseEntity fields (tenant-level only)
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    print("✅ Risks table created")

    # ============================================================================
    # DEPENDENCIES TABLE (Dependency Management)
    # ============================================================================
    print("\n📊 Creating dependencies table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dependencies (
            id SERIAL PRIMARY KEY,

            -- Identifiers (NO external_id - can be created manually or from Jira links)
            name VARCHAR(255),
            description TEXT,

            -- Dependency Type
            dependency_type VARCHAR(50),      -- blocks, is_blocked_by, relates_to, requires

            -- Dependency Status
            state VARCHAR(50),                -- open, in_progress, resolved, deferred, cancelled
            criticality VARCHAR(50),          -- low, medium, high, critical

            -- Cross-team tracking
            dependent_team VARCHAR(255),
            is_cross_team BOOLEAN DEFAULT FALSE,
            is_cross_program BOOLEAN DEFAULT FALSE,
            is_external BOOLEAN DEFAULT FALSE,

            -- Resolution
            resolution_notes TEXT,

            -- Ownership
            owner VARCHAR(255),

            -- Dates
            signed_off_date TIMESTAMP,
            target_resolution_date TIMESTAMP,
            critical_resolution_date TIMESTAMP,
            actual_resolution_date TIMESTAMP,

            -- IntegrationBaseEntity fields
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    print("✅ Dependencies table created")

    # ============================================================================
    # OBJECTIVES TABLE (OKR Framework)
    # ============================================================================
    print("\n📊 Creating objectives table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS objectives (
            id SERIAL PRIMARY KEY,

            -- Identifiers (NO external_id - manually created)
            title VARCHAR(500) NOT NULL,
            description TEXT,

            -- OKR Classification
            objective_type VARCHAR(50),       -- business, technical, cultural, customer

            -- Scope/Level (mutually exclusive - only ONE should be set)
            team_name VARCHAR(255),
            program_id INTEGER REFERENCES programs(id),
            portfolio_id INTEGER REFERENCES portfolios(id),

            -- Status
            state VARCHAR(50),                -- draft, active, completed, abandoned
            completion_percentage FLOAT,

            -- Dates
            start_date TIMESTAMP,
            target_date TIMESTAMP,
            completed_date TIMESTAMP,

            -- Ownership
            owner VARCHAR(255),

            -- IntegrationBaseEntity fields (tenant-level only)
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_updated_at TIMESTAMP DEFAULT NOW(),

            -- Ensure only one scope is set
            CONSTRAINT chk_objective_scope CHECK (
                (team_name IS NOT NULL AND program_id IS NULL AND portfolio_id IS NULL) OR
                (team_name IS NULL AND program_id IS NOT NULL AND portfolio_id IS NULL) OR
                (team_name IS NULL AND program_id IS NULL AND portfolio_id IS NOT NULL)
            )
        );
    """)
    print("✅ Objectives table created")

    # ============================================================================
    # KEY_RESULTS TABLE (OKR Key Results)
    # ============================================================================
    print("\n📊 Creating key_results table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS key_results (
            id SERIAL PRIMARY KEY,

            objective_id INTEGER NOT NULL REFERENCES objectives(id),

            -- Key Result Details
            title VARCHAR(500) NOT NULL,
            description TEXT,

            -- Measurement
            metric_type VARCHAR(50),          -- percentage, number, currency, boolean
            target_value FLOAT,
            current_value FLOAT,
            initial_value FLOAT,

            -- Status
            state VARCHAR(50),                -- on_track, at_risk, off_track, completed
            completion_percentage FLOAT,

            -- Dates
            target_date TIMESTAMP,
            completed_date TIMESTAMP,

            -- Ownership
            owner VARCHAR(255),

            -- IntegrationBaseEntity fields
            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),
            last_updated_at TIMESTAMP DEFAULT NOW()
        );
    """)
    print("✅ Key results table created")

    # ============================================================================
    # JUNCTION TABLES (Polymorphic Relationships)
    # ============================================================================
    print("\n📊 Creating risk junction tables...")

    # Risk-Program junction
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risks_programs (
            risk_id INTEGER REFERENCES risks(id),
            program_id INTEGER REFERENCES programs(id),
            PRIMARY KEY (risk_id, program_id)
        );
    """)

    # Risk-Portfolio junction
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risks_portfolios (
            risk_id INTEGER REFERENCES risks(id),
            portfolio_id INTEGER REFERENCES portfolios(id),
            PRIMARY KEY (risk_id, portfolio_id)
        );
    """)

    # Risk-Sprint junction
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risks_sprints (
            risk_id INTEGER REFERENCES risks(id),
            sprint_id INTEGER REFERENCES sprints(id),
            PRIMARY KEY (risk_id, sprint_id)
        );
    """)

    # Risk-WorkItem junction
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS risks_work_items (
            risk_id INTEGER REFERENCES risks(id),
            work_item_id INTEGER REFERENCES work_items(id),
            PRIMARY KEY (risk_id, work_item_id)
        );
    """)
    print("✅ Risk junction tables created (4 tables)")

    # Dependency-WorkItem junction
    print("\n📊 Creating dependency junction table...")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS dependencies_work_items (
            id SERIAL PRIMARY KEY,
            dependency_id INTEGER NOT NULL REFERENCES dependencies(id),
            work_item_id INTEGER NOT NULL REFERENCES work_items(id),

            -- Role in dependency
            role VARCHAR(50),                 -- source (blocking), target (blocked)

            tenant_id INTEGER NOT NULL REFERENCES tenants(id),
            active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT NOW(),

            CONSTRAINT uk_dependency_work_item UNIQUE(dependency_id, work_item_id, role)
        );
    """)
    print("✅ Dependency junction table created")

    # ============================================================================
    # INDEXES (Performance Optimization)
    # ============================================================================
    print("\n📊 Creating indexes...")

    # Portfolio indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolios_tenant_id ON portfolios(tenant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_portfolios_state ON portfolios(state);")

    # Program indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_programs_tenant_id ON programs(tenant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_programs_portfolio_id ON programs(portfolio_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_programs_state ON programs(state);")

    # Sprint indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sprints_tenant_id ON sprints(tenant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sprints_integration_id ON sprints(integration_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sprints_program_id ON sprints(program_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sprints_state ON sprints(state);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_sprints_board_id ON sprints(board_id);")

    # Work items sprints indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_sprints_work_item ON work_items_sprints(work_item_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_sprints_sprint ON work_items_sprints(sprint_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_sprints_outcome ON work_items_sprints(sprint_outcome);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_work_items_sprints_tenant ON work_items_sprints(tenant_id);")

    # Risk indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risks_tenant_id ON risks(tenant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risks_state ON risks(state);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_risks_risk_score ON risks(risk_score);")

    # Dependency indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_tenant_id ON dependencies(tenant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_state ON dependencies(state);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_criticality ON dependencies(criticality);")

    # Objective indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_objectives_tenant_id ON objectives(tenant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_objectives_team ON objectives(team_name) WHERE team_name IS NOT NULL;")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_objectives_program ON objectives(program_id) WHERE program_id IS NOT NULL;")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_objectives_portfolio ON objectives(portfolio_id) WHERE portfolio_id IS NOT NULL;")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_objectives_state ON objectives(state);")

    # Key result indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_key_results_objective ON key_results(objective_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_key_results_tenant ON key_results(tenant_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_key_results_state ON key_results(state);")

    # Dependencies work items indexes
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_work_items_dependency ON dependencies_work_items(dependency_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_work_items_work_item ON dependencies_work_items(work_item_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_dependencies_work_items_role ON dependencies_work_items(role);")

    print("✅ All indexes created")

    print("\n" + "=" * 80)
    print("✅ Migration 0005 completed successfully!")
    print("=" * 80)

def rollback(connection):
    """Rollback the portfolio management schema migration."""
    print("📋 Rolling back Migration 0005: Portfolio Management Schema")
    print("=" * 80)

    cursor = connection.cursor()

    # Drop tables in reverse dependency order
    tables_to_drop = [
        'dependencies_work_items',
        'risks_work_items',
        'risks_sprints',
        'risks_portfolios',
        'risks_programs',
        'key_results',
        'objectives',
        'dependencies',
        'risks',
        'work_items_sprints',
        'sprints',
        'programs',
        'portfolios'
    ]

    for table in tables_to_drop:
        print(f"🗑️  Dropping table: {table}")
        cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE;")

    print("\n" + "=" * 80)
    print("✅ Migration 0005 rollback completed successfully!")
    print("=" * 80)

def main():
    """Main migration execution function."""
    parser = argparse.ArgumentParser(description='Migration 0005: Portfolio Management Schema')
    parser.add_argument('--rollback', action='store_true', help='Rollback the migration')
    args = parser.parse_args()

    connection = None
    try:
        connection = get_database_connection()

        if args.rollback:
            rollback(connection)
        else:
            apply(connection)

        connection.commit()

    except Exception as e:
        if connection:
            connection.rollback()
        print(f"\n❌ Migration failed: {e}")
        raise
    finally:
        if connection:
            connection.close()

if __name__ == "__main__":
    main()

