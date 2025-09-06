/**
 * WorkItem List Component with ML fields support
 * Phase 1-6: Frontend Service Compatibility
 */

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { WorkItem, WorkItemsResponse } from '../types';
import apiService from '../services/apiService';

interface WorkItemListProps {
  clientId: number;
  showMlFields?: boolean;
  limit?: number;
  projectKey?: string;
  status?: string;
  assignee?: string;
  className?: string;
}

export const WorkItemList: React.FC<WorkItemListProps> = ({
  clientId,
  showMlFields = false,
  limit = 50,
  projectKey,
  status,
  assignee,
  className = '',
}) => {
  const [issuesResponse, setWorkItemsResponse] = useState<WorkItemsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchWorkItems = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await apiService.getWorkItems(clientId, {
          limit,
          include_ml_fields: showMlFields,
          project_key: projectKey,
          status,
          assignee,
        });

        setWorkItemsResponse(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch issues');
      } finally {
        setLoading(false);
      }
    };

    fetchWorkItems();
  }, [clientId, showMlFields, limit, projectKey, status, assignee]);

  if (loading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        <span className="ml-2 text-secondary">Loading issues...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className={`p-4 bg-red-50 border border-red-200 rounded-lg ${className}`}>
        <div className="flex items-center">
          <div className="text-red-600">
            <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
              <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
            </svg>
          </div>
          <div className="ml-3">
            <h3 className="text-sm font-medium text-red-800">Error loading issues</h3>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!issuesResponse || issuesResponse.issues.length === 0) {
    return (
      <div className={`text-center p-8 ${className}`}>
        <div className="text-secondary">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-secondary">No issues found</h3>
          <p className="mt-1 text-sm text-tertiary">Try adjusting your filters or check back later.</p>
        </div>
      </div>
    );
  }

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <h2 className="text-lg font-semibold text-primary">
            WorkItems ({issuesResponse.total_count})
          </h2>
          {issuesResponse.ml_fields_included && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
              ML Enhanced
            </span>
          )}
        </div>
        {issuesResponse.count < issuesResponse.total_count && (
          <span className="text-sm text-tertiary">
            Showing {issuesResponse.count} of {issuesResponse.total_count}
          </span>
        )}
      </div>

      {/* WorkItems List */}
      <div className="space-y-3">
        {issuesResponse.issues.map((issue, index) => (
          <motion.div
            key={issue.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            className="bg-card border border-border rounded-lg p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                {/* WorkItem Header */}
                <div className="flex items-center space-x-2 mb-2">
                  <h3 className="text-sm font-medium text-primary truncate">
                    {issue.key}: {issue.summary}
                  </h3>
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                    issue.status_name === 'Done' ? 'bg-green-100 text-green-800' :
                    issue.status_name === 'In Progress' ? 'bg-blue-100 text-blue-800' :
                    'bg-gray-100 text-gray-800'
                  }`}>
                    {issue.status_name}
                  </span>
                </div>

                {/* WorkItem Details */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-secondary">
                  <div>
                    <span className="font-medium">Type:</span> {issue.wit_name}
                  </div>
                  {issue.assignee && (
                    <div>
                      <span className="font-medium">Assignee:</span> {issue.assignee}
                    </div>
                  )}
                  {issue.story_points && (
                    <div>
                      <span className="font-medium">Story Points:</span> {issue.story_points}
                    </div>
                  )}
                  {issue.priority && (
                    <div>
                      <span className="font-medium">Priority:</span> {issue.priority}
                    </div>
                  )}
                </div>

                {/* Description */}
                {issue.description && (
                  <p className="mt-2 text-sm text-tertiary line-clamp-2">
                    {issue.description}
                  </p>
                )}

                {/* ML Fields - Only show if enabled and data exists */}
                {showMlFields && (issue.ml_estimated_story_points || issue.ml_estimation_confidence || issue.embedding) && (
                  <div className="mt-3 p-3 bg-blue-50 border border-blue-200 rounded-md">
                    <h4 className="text-xs font-medium text-blue-800 mb-2">ML Insights</h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-blue-700">
                      {issue.ml_estimated_story_points && (
                        <div>
                          <span className="font-medium">ML Estimated Points:</span> {issue.ml_estimated_story_points}
                        </div>
                      )}
                      {issue.ml_estimation_confidence && (
                        <div>
                          <span className="font-medium">Confidence:</span> {issue.ml_estimation_confidence}
                        </div>
                      )}
                      {issue.embedding && (
                        <div>
                          <span className="font-medium">Vector Embedding:</span> Available ({issue.embedding.length} dimensions)
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* WorkItem Actions */}
              <div className="flex items-center space-x-2 ml-4">
                <button
                  onClick={() => window.open(`/issues/${issue.id}`, '_blank')}
                  className="text-blue-600 hover:text-blue-800 text-sm font-medium"
                >
                  View
                </button>
              </div>
            </div>

            {/* Timestamps */}
            <div className="mt-3 pt-3 border-t border-border flex justify-between text-xs text-tertiary">
              <span>Created: {new Date(issue.created_at).toLocaleDateString()}</span>
              <span>Updated: {new Date(issue.updated_at).toLocaleDateString()}</span>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Load More Button */}
      {issuesResponse.count < issuesResponse.total_count && (
        <div className="text-center pt-4">
          <button className="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors">
            Load More WorkItems
          </button>
        </div>
      )}
    </div>
  );
};

export default WorkItemList;
