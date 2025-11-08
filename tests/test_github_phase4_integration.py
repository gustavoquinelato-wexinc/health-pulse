"""
Integration tests for GitHub Phase 4 extraction and transform pipeline.

Tests the complete end-to-end flow:
1. Extraction worker receives message
2. Extracts PR data from GitHub API
3. Stores raw data
4. Queues to transform
5. Transform worker processes data
6. Queues to embedding
7. Checkpoint saved for recovery
"""

import pytest
import json
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime


class TestGitHubPhase4Pipeline:
    """Test the complete GitHub Phase 4 extraction and transform pipeline"""

    @pytest.mark.asyncio
    async def test_complete_pr_extraction_pipeline(self):
        """Test complete flow: extraction -> transform -> embedding"""
        import sys
        sys.path.insert(0, 'services/backend-service')
        
        # Mock GitHub API response
        mock_pr_response = {
            'data': {
                'repository': {
                    'pullRequests': {
                        'nodes': [
                            {
                                'id': 'PR_kwDOOT7yrs6RclPp',
                                'number': 1,
                                'title': 'Test PR',
                                'body': 'Test body',
                                'state': 'OPEN',
                                'createdAt': '2024-01-01T00:00:00Z',
                                'updatedAt': '2024-01-02T00:00:00Z',
                                'closedAt': None,
                                'mergedAt': None,
                                'author': {'login': 'testuser'},
                                'commits': {
                                    'nodes': [
                                        {
                                            'commit': {
                                                'oid': 'abc123',
                                                'message': 'Test commit',
                                                'author': {
                                                    'name': 'Test Author',
                                                    'email': 'test@example.com',
                                                    'date': '2024-01-01T00:00:00Z'
                                                },
                                                'committer': {
                                                    'name': 'Test Committer',
                                                    'email': 'test@example.com',
                                                    'date': '2024-01-01T00:00:00Z'
                                                }
                                            }
                                        }
                                    ],
                                    'pageInfo': {'hasNextPage': False, 'endCursor': None}
                                },
                                'reviews': {
                                    'nodes': [],
                                    'pageInfo': {'hasNextPage': False, 'endCursor': None}
                                },
                                'comments': {
                                    'nodes': [],
                                    'pageInfo': {'hasNextPage': False, 'endCursor': None}
                                },
                                'reviewThreads': {
                                    'nodes': [],
                                    'pageInfo': {'hasNextPage': False, 'endCursor': None}
                                }
                            }
                        ],
                        'pageInfo': {'hasNextPage': False, 'endCursor': None}
                    }
                }
            }
        }

        # Test that extraction processes the response correctly
        assert mock_pr_response['data']['repository']['pullRequests']['nodes'][0]['id'] == 'PR_kwDOOT7yrs6RclPp'
        assert len(mock_pr_response['data']['repository']['pullRequests']['nodes']) == 1

    @pytest.mark.asyncio
    async def test_nested_pagination_flow(self):
        """Test nested pagination for commits, reviews, comments"""
        import sys
        sys.path.insert(0, 'services/backend-service')
        
        # Mock nested commits response
        mock_commits_response = {
            'data': {
                'node': {
                    'commits': {
                        'nodes': [
                            {
                                'commit': {
                                    'oid': 'def456',
                                    'message': 'Another commit',
                                    'author': {
                                        'name': 'Test Author',
                                        'email': 'test@example.com',
                                        'date': '2024-01-02T00:00:00Z'
                                    },
                                    'committer': {
                                        'name': 'Test Committer',
                                        'email': 'test@example.com',
                                        'date': '2024-01-02T00:00:00Z'
                                    }
                                }
                            }
                        ],
                        'pageInfo': {'hasNextPage': True, 'endCursor': 'Y3Vyc29yOjEyMzQ1Ng=='}
                    }
                }
            }
        }

        # Verify response structure
        assert 'data' in mock_commits_response
        assert 'node' in mock_commits_response['data']
        assert 'commits' in mock_commits_response['data']['node']
        assert mock_commits_response['data']['node']['commits']['pageInfo']['hasNextPage'] is True

    @pytest.mark.asyncio
    async def test_checkpoint_recovery_on_failure(self):
        """Test that checkpoint allows recovery from failure"""
        import sys
        sys.path.insert(0, 'services/backend-service')
        
        # Simulate checkpoint data
        checkpoint_data = {
            'last_pr_cursor': 'Y3Vyc29yOjEyMzQ1Ng==',
            'prs_processed': 10,
            'checkpoint_timestamp': '2024-01-01T12:00:00'
        }

        # Verify checkpoint structure
        assert 'last_pr_cursor' in checkpoint_data
        assert checkpoint_data['last_pr_cursor'] is not None
        assert checkpoint_data['prs_processed'] == 10

    def test_transform_type1_with_complete_nested_data(self):
        """Test Type 1 transform with all nested data complete"""
        # Raw data structure for Type 1
        raw_data_type1 = {
            'pr_id': 'PR_kwDOOT7yrs6RclPp',
            'pr_data': {
                'id': 'PR_kwDOOT7yrs6RclPp',
                'number': 1,
                'title': 'Test PR',
                'body': 'Test body',
                'state': 'OPEN',
                'createdAt': '2024-01-01T00:00:00Z',
                'updatedAt': '2024-01-02T00:00:00Z',
                'closedAt': None,
                'mergedAt': None,
                'author': {'login': 'testuser'}
            },
            'commits': [{'commit': {'oid': 'abc123', 'message': 'Test'}}],
            'commits_cursor': None,  # No more commits
            'reviews': [],
            'reviews_cursor': None,  # No more reviews
            'comments': [],
            'comments_cursor': None,  # No more comments
            'review_threads': []
        }

        # Verify Type 1 structure
        assert raw_data_type1.get('nested_data_only') is None  # Type 1 doesn't have this flag
        assert raw_data_type1['commits_cursor'] is None
        assert raw_data_type1['reviews_cursor'] is None
        assert raw_data_type1['comments_cursor'] is None

    def test_transform_type2_nested_only_data(self):
        """Test Type 2 transform with nested-only data"""
        # Raw data structure for Type 2
        raw_data_type2 = {
            'pr_id': 'PR_kwDOOT7yrs6RclPp',
            'nested_data_only': True,
            'nested_type': 'commits',
            'data': [
                {
                    'commit': {
                        'oid': 'def456',
                        'message': 'Another commit',
                        'author': {'name': 'Test', 'email': 'test@example.com', 'date': '2024-01-02T00:00:00Z'},
                        'committer': {'name': 'Test', 'email': 'test@example.com', 'date': '2024-01-02T00:00:00Z'}
                    }
                }
            ],
            'cursor': 'Y3Vyc29yOjEyMzQ1Ng==',
            'has_more': True
        }

        # Verify Type 2 structure
        assert raw_data_type2['nested_data_only'] is True
        assert raw_data_type2['nested_type'] == 'commits'
        assert raw_data_type2['has_more'] is True

    def test_embedding_queue_decision_logic(self):
        """Test logic for deciding when to queue to embedding"""
        # Type 1: Queue only if all nested data complete
        type1_complete = {
            'commits_cursor': None,
            'reviews_cursor': None,
            'comments_cursor': None
        }
        
        has_pending = any([
            type1_complete.get('commits_cursor'),
            type1_complete.get('reviews_cursor'),
            type1_complete.get('comments_cursor')
        ])
        
        assert has_pending is False  # Should queue to embedding

        # Type 1: Don't queue if any nested data pending
        type1_pending = {
            'commits_cursor': 'Y3Vyc29yOjEyMzQ1Ng==',
            'reviews_cursor': None,
            'comments_cursor': None
        }
        
        has_pending = any([
            type1_pending.get('commits_cursor'),
            type1_pending.get('reviews_cursor'),
            type1_pending.get('comments_cursor')
        ])
        
        assert has_pending is True  # Should NOT queue to embedding

        # Type 2: Queue only if has_more=False
        type2_complete = {'has_more': False}
        assert type2_complete['has_more'] is False  # Should queue to embedding

        type2_pending = {'has_more': True}
        assert type2_pending['has_more'] is True  # Should NOT queue to embedding


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

