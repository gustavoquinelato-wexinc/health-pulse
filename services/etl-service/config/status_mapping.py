#!/usr/bin/env python3
"""
Status Mapping Configuration for ETL Service.

This file contains the mapping from various Jira status names to standardized flow steps.
Each mapping entry defines how a specific status should be mapped to a standardized flow step.
"""

# Standardized status mapping for Jira statuses to flow steps
STATUS_MAPPING = [
    # BACKLOG
    {"status_from": "--creation--", "status_to": "Backlog", "status_category": "To Do"},
    {"status_from": "backlog", "status_to": "Backlog", "status_category": "To Do"},
    {"status_from": "new", "status_to": "Backlog", "status_category": "To Do"},
    {"status_from": "open", "status_to": "Backlog", "status_category": "To Do"},
    {"status_from": "created", "status_to": "Backlog", "status_category": "To Do"},
    {"status_from": "(backlog) unprioritized to dos", "status_to": "Backlog", "status_category": "To Do"},
    
    # REFINEMENT
    {"status_from": "analysis", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "design", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "prerefinement", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "ready to refine", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "refinement", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "refining", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "tech review", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "waiting for refinement", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "in triage", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "pending approval", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "discovery", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "composting", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "onboarding templates", "status_to": "Refinement", "status_category": "To Do"},
    {"status_from": "templates", "status_to": "Refinement", "status_category": "To Do"},
    
    # READY TO WORK
    {"status_from": "approved", "status_to": "Ready to Work", "status_category": "To Do"},
    {"status_from": "ready", "status_to": "Ready to Work", "status_category": "To Do"},
    {"status_from": "ready for development", "status_to": "Ready to Work", "status_category": "To Do"},
    {"status_from": "ready to development", "status_to": "Ready to Work", "status_category": "To Do"},
    {"status_from": "ready to work", "status_to": "Ready to Work", "status_category": "To Do"},
    {"status_from": "refined", "status_to": "Ready to Work", "status_category": "To Do"},
    {"status_from": "proposed", "status_to": "Ready to Work", "status_category": "To Do"},
    
    # TO DO
    {"status_from": "committed", "status_to": "To Do", "status_category": "To Do"},
    {"status_from": "planned", "status_to": "To Do", "status_category": "To Do"},
    {"status_from": "selected for development", "status_to": "To Do", "status_category": "To Do"},
    {"status_from": "to do", "status_to": "To Do", "status_category": "To Do"},
    
    # IN PROGRESS
    {"status_from": "active", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "applied to trn", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "blocked", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "building", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "code review", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "codereview", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "coding", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "coding done", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "deployed to dev", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "development", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "in development", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "in progress", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "in review", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "peer review", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "pre-readiness", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "ready for peer review", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "ready to dep to dev", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "review", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "training", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "validated in trn", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "waiting partner", "status_to": "In Progress", "status_category": "In Progress"},
    {"status_from": "on hold", "status_to": "In Progress", "status_category": "In Progress"},

    # READY FOR QA TESTING
    {"status_from": "ready for qa", "status_to": "Ready for Story Testing", "status_category": "Waiting"},
    {"status_from": "ready for qa build", "status_to": "Ready for Story Testing", "status_category": "Waiting"},
    {"status_from": "ready for test", "status_to": "Ready for Story Testing", "status_category": "Waiting"},
    {"status_from": "ready for testing", "status_to": "Ready for Story Testing", "status_category": "Waiting"},
    {"status_from": "ready for story testing", "status_to": "Ready for Story Testing", "status_category": "Waiting"},

    # IN QA TEST
    {"status_from": "applied to qa", "status_to": "Story Testing", "status_category": "In Progress"},
    {"status_from": "in test", "status_to": "Story Testing", "status_category": "In Progress"},
    {"status_from": "in testing", "status_to": "Story Testing", "status_category": "In Progress"},
    {"status_from": "promoted to qa", "status_to": "Story Testing", "status_category": "In Progress"},
    {"status_from": "qa", "status_to": "Story Testing", "status_category": "In Progress"},
    {"status_from": "qa in progress", "status_to": "Story Testing", "status_category": "In Progress"},
    {"status_from": "test", "status_to": "Story Testing", "status_category": "In Progress"},
    {"status_from": "story testing", "status_to": "Story Testing", "status_category": "In Progress"},
    {"status_from": "testing", "status_to": "Story Testing", "status_category": "In Progress"},

    # READY FOR UAT TESTING
    {"status_from": "ready for uat", "status_to": "Ready for Acceptance", "status_category": "Waiting"},
    {"status_from": "ready for stage", "status_to": "Ready for Acceptance", "status_category": "Waiting"},
    {"status_from": "validated in qa", "status_to": "Ready for Acceptance", "status_category": "Waiting"},
    {"status_from": "ready for demo", "status_to": "Ready for Acceptance", "status_category": "Waiting"},
    {"status_from": "ready for acceptance", "status_to": "Ready for Acceptance", "status_category": "Waiting"},

    # IN UAT TEST
    {"status_from": "applied to stg", "status_to": "Acceptance Testing", "status_category": "In Progress"},
    {"status_from": "applied to uat", "status_to": "Acceptance Testing", "status_category": "In Progress"},
    {"status_from": "in stage testing", "status_to": "Acceptance Testing", "status_category": "In Progress"},
    {"status_from": "promoted to uat", "status_to": "Acceptance Testing", "status_category": "In Progress"},
    {"status_from": "regression testing", "status_to": "Acceptance Testing", "status_category": "In Progress"},
    {"status_from": "release approval pending", "status_to": "Acceptance Testing", "status_category": "In Progress"},
    {"status_from": "uat", "status_to": "Acceptance Testing", "status_category": "In Progress"},
    {"status_from": "acceptance testing", "status_to": "Acceptance Testing", "status_category": "In Progress"},

    # READY FOR PROD
    {"status_from": "deploy", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "deployment", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "ready for prod", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "ready for prd", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "ready for production", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "ready for release", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "ready to dep to prod", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "ready to launch", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "release pending", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "resolved", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "validated in stg", "status_to": "Ready for Prod", "status_category": "Waiting"},
    {"status_from": "validated in uat", "status_to": "Ready for Prod", "status_category": "Waiting"},

    # DONE
    {"status_from": "applied to prod", "status_to": "Done", "status_category": "Done"},
    {"status_from": "applied to prod/trn", "status_to": "Done", "status_category": "Done"},
    {"status_from": "closed", "status_to": "Done", "status_category": "Done"},
    {"status_from": "done", "status_to": "Done", "status_category": "Done"},
    {"status_from": "validated in prod", "status_to": "Done", "status_category": "Done"},
    {"status_from": "released", "status_to": "Done", "status_category": "Done"},

    # REMOVED
    {"status_from": "cancelled", "status_to": "Discarded", "status_category": "Discarded"},
    {"status_from": "rejected", "status_to": "Discarded", "status_category": "Discarded"},
    {"status_from": "removed", "status_to": "Discarded", "status_category": "Discarded"},
    {"status_from": "withdrawn", "status_to": "Discarded", "status_category": "Discarded"},
]


def get_status_mapping():
    """Get the status mapping configuration."""
    return STATUS_MAPPING


def find_flow_step_for_status(status_name):
    """Find the flow step mapping for a given status name."""
    status_lower = status_name.lower().strip()

    for mapping in STATUS_MAPPING:
        if mapping["status_from"].lower() == status_lower:
            return {
                "flow_step_name": mapping["status_to"],
                "step_category": mapping["status_category"]
            }

    # Return None if no mapping found
    return None
