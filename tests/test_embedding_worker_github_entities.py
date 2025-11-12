"""
Test embedding worker text extraction for GitHub entity types.
"""

import pytest
import sys
sys.path.insert(0, 'services/backend-service')

from app.etl.github.github_embedding_worker import GitHubEmbeddingWorker


class TestEmbeddingWorkerTextExtraction:
    """Test _extract_text_content method for GitHub entity types"""

    def setup_method(self):
        """Setup test fixtures"""
        self.worker = GitHubEmbeddingWorker()

    def test_extract_text_for_prs_commits(self):
        """Test text extraction for PR commits"""
        entity_data = {
            'id': 1,
            'external_id': 'abc123',
            'message': 'Fix bug in authentication',
            'author_name': 'John Doe',
            'author_email': 'john@example.com',
            'committer_name': 'Jane Smith',
            'committer_email': 'jane@example.com',
            'entity_type': 'prs_commits',
            'tenant_id': 1
        }
        
        text = self.worker._extract_text_content(entity_data, 'prs_commits')
        
        assert text is not None
        assert len(text) > 0
        assert 'Fix bug in authentication' in text
        assert 'John Doe' in text
        assert 'john@example.com' in text
        assert 'Jane Smith' in text

    def test_extract_text_for_prs_reviews(self):
        """Test text extraction for PR reviews"""
        entity_data = {
            'id': 2,
            'external_id': 'review123',
            'body': 'Looks good, but needs some changes',
            'state': 'CHANGES_REQUESTED',
            'author_login': 'reviewer1',
            'submitted_at': '2025-10-29T10:00:00Z',
            'entity_type': 'prs_reviews',
            'tenant_id': 1
        }
        
        text = self.worker._extract_text_content(entity_data, 'prs_reviews')
        
        assert text is not None
        assert len(text) > 0
        assert 'Looks good, but needs some changes' in text
        assert 'CHANGES_REQUESTED' in text
        assert 'reviewer1' in text

    def test_extract_text_for_prs_comments(self):
        """Test text extraction for PR comments"""
        entity_data = {
            'id': 3,
            'external_id': 'comment123',
            'body': 'This line needs to be refactored',
            'author_login': 'commenter1',
            'comment_type': 'REVIEW',
            'path': 'src/auth.py',
            'line': 42,
            'entity_type': 'prs_comments',
            'tenant_id': 1
        }
        
        text = self.worker._extract_text_content(entity_data, 'prs_comments')
        
        assert text is not None
        assert len(text) > 0
        assert 'This line needs to be refactored' in text
        assert 'commenter1' in text

    def test_extract_text_for_prs(self):
        """Test text extraction for PRs"""
        entity_data = {
            'id': 4,
            'external_id': 'PR_kwDOPT-gOs6wLqG5',
            'title': 'Add new authentication feature',
            'description': 'This PR adds OAuth2 support',
            'entity_type': 'prs',
            'tenant_id': 1
        }
        
        text = self.worker._extract_text_content(entity_data, 'prs')
        
        assert text is not None
        assert len(text) > 0
        assert 'Add new authentication feature' in text
        assert 'This PR adds OAuth2 support' in text

    def test_extract_text_returns_empty_for_missing_fields(self):
        """Test that extraction returns empty string when no fields are present"""
        entity_data = {
            'id': 5,
            'external_id': 'empty123',
            'entity_type': 'prs_commits',
            'tenant_id': 1
        }
        
        text = self.worker._extract_text_content(entity_data, 'prs_commits')
        
        # Should return empty string, not None
        assert text == ''

    def test_extract_text_handles_partial_data(self):
        """Test that extraction handles partial data gracefully"""
        entity_data = {
            'id': 6,
            'external_id': 'partial123',
            'message': 'Partial commit message',
            # Missing author_name, author_email, etc.
            'entity_type': 'prs_commits',
            'tenant_id': 1
        }
        
        text = self.worker._extract_text_content(entity_data, 'prs_commits')
        
        assert text is not None
        assert 'Partial commit message' in text

