-- Fix missing primary keys and foreign keys in source database
-- Based on migration 001_initial_schema.py and unified_models.py
-- Run this against pulse_db to add proper constraints

-- Add missing primary keys (from migration lines 682-706)
DO $$
BEGIN
    -- Add primary keys only if they don't exist
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_clients') THEN
        ALTER TABLE clients ADD CONSTRAINT pk_clients PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_users') THEN
        ALTER TABLE users ADD CONSTRAINT pk_users PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_integrations') THEN
        ALTER TABLE integrations ADD CONSTRAINT pk_integrations PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_projects') THEN
        ALTER TABLE projects ADD CONSTRAINT pk_projects PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_issuetypes') THEN
        ALTER TABLE issuetypes ADD CONSTRAINT pk_issuetypes PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_statuses') THEN
        ALTER TABLE statuses ADD CONSTRAINT pk_statuses PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_issues') THEN
        ALTER TABLE issues ADD CONSTRAINT pk_issues PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_issue_changelogs') THEN
        ALTER TABLE issue_changelogs ADD CONSTRAINT pk_issue_changelogs PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_repositories') THEN
        ALTER TABLE repositories ADD CONSTRAINT pk_repositories PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_pull_requests') THEN
        ALTER TABLE pull_requests ADD CONSTRAINT pk_pull_requests PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_pull_request_commits') THEN
        ALTER TABLE pull_request_commits ADD CONSTRAINT pk_pull_request_commits PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_pull_request_reviews') THEN
        ALTER TABLE pull_request_reviews ADD CONSTRAINT pk_pull_request_reviews PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_pull_request_comments') THEN
        ALTER TABLE pull_request_comments ADD CONSTRAINT pk_pull_request_comments PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_jira_pull_request_links') THEN
        ALTER TABLE jira_pull_request_links ADD CONSTRAINT pk_jira_pull_request_links PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_workflows') THEN
        ALTER TABLE workflows ADD CONSTRAINT pk_workflows PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_status_mappings') THEN
        ALTER TABLE status_mappings ADD CONSTRAINT pk_status_mappings PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_issuetype_mappings') THEN
        ALTER TABLE issuetype_mappings ADD CONSTRAINT pk_issuetype_mappings PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_issuetype_hierarchies') THEN
        ALTER TABLE issuetype_hierarchies ADD CONSTRAINT pk_issuetype_hierarchies PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_projects_issuetypes') THEN
        ALTER TABLE projects_issuetypes ADD CONSTRAINT pk_projects_issuetypes PRIMARY KEY (project_id, issuetype_id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_projects_statuses') THEN
        ALTER TABLE projects_statuses ADD CONSTRAINT pk_projects_statuses PRIMARY KEY (project_id, status_id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_job_schedules') THEN
        ALTER TABLE job_schedules ADD CONSTRAINT pk_job_schedules PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_user_sessions') THEN
        ALTER TABLE user_sessions ADD CONSTRAINT pk_user_sessions PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_user_permissions') THEN
        ALTER TABLE user_permissions ADD CONSTRAINT pk_user_permissions PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_system_settings') THEN
        ALTER TABLE system_settings ADD CONSTRAINT pk_system_settings PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_dora_market_benchmarks') THEN
        ALTER TABLE dora_market_benchmarks ADD CONSTRAINT pk_dora_market_benchmarks PRIMARY KEY (id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'pk_dora_metric_insights') THEN
        ALTER TABLE dora_metric_insights ADD CONSTRAINT pk_dora_metric_insights PRIMARY KEY (id);
    END IF;
END $$;

-- Add missing foreign keys (based on unified_models.py relationships)
DO $$
BEGIN
    -- Users table foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_users_client_id') THEN
        ALTER TABLE users ADD CONSTRAINT fk_users_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    -- Integrations table foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_integrations_client_id') THEN
        ALTER TABLE integrations ADD CONSTRAINT fk_integrations_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    -- Projects table foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_projects_client_id') THEN
        ALTER TABLE projects ADD CONSTRAINT fk_projects_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_projects_integration_id') THEN
        ALTER TABLE projects ADD CONSTRAINT fk_projects_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);
    END IF;

    -- Issuetypes table foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_issuetypes_client_id') THEN
        ALTER TABLE issuetypes ADD CONSTRAINT fk_issuetypes_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_issuetypes_integration_id') THEN
        ALTER TABLE issuetypes ADD CONSTRAINT fk_issuetypes_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);
    END IF;

    -- Statuses table foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_statuses_client_id') THEN
        ALTER TABLE statuses ADD CONSTRAINT fk_statuses_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_statuses_integration_id') THEN
        ALTER TABLE statuses ADD CONSTRAINT fk_statuses_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);
    END IF;

    -- Issues table foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_issues_client_id') THEN
        ALTER TABLE issues ADD CONSTRAINT fk_issues_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_issues_integration_id') THEN
        ALTER TABLE issues ADD CONSTRAINT fk_issues_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_issues_project_id') THEN
        ALTER TABLE issues ADD CONSTRAINT fk_issues_project_id FOREIGN KEY (project_id) REFERENCES projects(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_issues_issuetype_id') THEN
        ALTER TABLE issues ADD CONSTRAINT fk_issues_issuetype_id FOREIGN KEY (issuetype_id) REFERENCES issuetypes(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_issues_status_id') THEN
        ALTER TABLE issues ADD CONSTRAINT fk_issues_status_id FOREIGN KEY (status_id) REFERENCES statuses(id);
    END IF;

    -- Issue changelogs foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_issue_changelogs_issue_id') THEN
        ALTER TABLE issue_changelogs ADD CONSTRAINT fk_issue_changelogs_issue_id FOREIGN KEY (issue_id) REFERENCES issues(id);
    END IF;

    -- Repositories foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_repositories_client_id') THEN
        ALTER TABLE repositories ADD CONSTRAINT fk_repositories_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    -- Pull requests foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_pull_requests_repository_id') THEN
        ALTER TABLE pull_requests ADD CONSTRAINT fk_pull_requests_repository_id FOREIGN KEY (repository_id) REFERENCES repositories(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_pull_requests_issue_id') THEN
        ALTER TABLE pull_requests ADD CONSTRAINT fk_pull_requests_issue_id FOREIGN KEY (issue_id) REFERENCES issues(id);
    END IF;

    -- Pull request related tables
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_pull_request_commits_pull_request_id') THEN
        ALTER TABLE pull_request_commits ADD CONSTRAINT fk_pull_request_commits_pull_request_id FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_pull_request_reviews_pull_request_id') THEN
        ALTER TABLE pull_request_reviews ADD CONSTRAINT fk_pull_request_reviews_pull_request_id FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_pull_request_comments_pull_request_id') THEN
        ALTER TABLE pull_request_comments ADD CONSTRAINT fk_pull_request_comments_pull_request_id FOREIGN KEY (pull_request_id) REFERENCES pull_requests(id);
    END IF;

    -- Jira PR links
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_jira_pull_request_links_issue_id') THEN
        ALTER TABLE jira_pull_request_links ADD CONSTRAINT fk_jira_pull_request_links_issue_id FOREIGN KEY (issue_id) REFERENCES issues(id);
    END IF;

    -- Workflows foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_workflows_client_id') THEN
        ALTER TABLE workflows ADD CONSTRAINT fk_workflows_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_workflows_integration_id') THEN
        ALTER TABLE workflows ADD CONSTRAINT fk_workflows_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);
    END IF;

    -- Status mappings foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_status_mappings_client_id') THEN
        ALTER TABLE status_mappings ADD CONSTRAINT fk_status_mappings_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_status_mappings_workflow_id') THEN
        ALTER TABLE status_mappings ADD CONSTRAINT fk_status_mappings_workflow_id FOREIGN KEY (workflow_id) REFERENCES workflows(id);
    END IF;

    -- Issuetype mappings and hierarchies
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_issuetype_mappings_client_id') THEN
        ALTER TABLE issuetype_mappings ADD CONSTRAINT fk_issuetype_mappings_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_issuetype_hierarchies_client_id') THEN
        ALTER TABLE issuetype_hierarchies ADD CONSTRAINT fk_issuetype_hierarchies_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    -- Relationship tables
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_projects_issuetypes_project_id') THEN
        ALTER TABLE projects_issuetypes ADD CONSTRAINT fk_projects_issuetypes_project_id FOREIGN KEY (project_id) REFERENCES projects(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_projects_issuetypes_issuetype_id') THEN
        ALTER TABLE projects_issuetypes ADD CONSTRAINT fk_projects_issuetypes_issuetype_id FOREIGN KEY (issuetype_id) REFERENCES issuetypes(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_projects_statuses_project_id') THEN
        ALTER TABLE projects_statuses ADD CONSTRAINT fk_projects_statuses_project_id FOREIGN KEY (project_id) REFERENCES projects(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_projects_statuses_status_id') THEN
        ALTER TABLE projects_statuses ADD CONSTRAINT fk_projects_statuses_status_id FOREIGN KEY (status_id) REFERENCES statuses(id);
    END IF;

    -- Job schedules foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_job_schedules_integration_id') THEN
        ALTER TABLE job_schedules ADD CONSTRAINT fk_job_schedules_integration_id FOREIGN KEY (integration_id) REFERENCES integrations(id);
    END IF;

    -- User related tables
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_sessions_user_id') THEN
        ALTER TABLE user_sessions ADD CONSTRAINT fk_user_sessions_user_id FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_user_permissions_user_id') THEN
        ALTER TABLE user_permissions ADD CONSTRAINT fk_user_permissions_user_id FOREIGN KEY (user_id) REFERENCES users(id);
    END IF;

    -- System settings foreign keys
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_system_settings_client_id') THEN
        ALTER TABLE system_settings ADD CONSTRAINT fk_system_settings_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
    END IF;

    -- DORA tables foreign keys (if they have client_id)
    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'dora_market_benchmarks' AND column_name = 'client_id') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_dora_market_benchmarks_client_id') THEN
            ALTER TABLE dora_market_benchmarks ADD CONSTRAINT fk_dora_market_benchmarks_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
        END IF;
    END IF;

    IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'dora_metric_insights' AND column_name = 'client_id') THEN
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fk_dora_metric_insights_client_id') THEN
            ALTER TABLE dora_metric_insights ADD CONSTRAINT fk_dora_metric_insights_client_id FOREIGN KEY (client_id) REFERENCES clients(id);
        END IF;
    END IF;
END $$;
