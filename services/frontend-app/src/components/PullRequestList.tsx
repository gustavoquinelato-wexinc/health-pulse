/**
 * Pull Request List Component with ML fields support
 * Phase 1-6: Frontend Service Compatibility
 */

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Pr, PrsResponse } from '../types';
import apiService from '../services/apiService';

interface PrListProps {
  clientId: number;
  showMlFields?: boolean;
  limit?: number;
  repository?: string;
  status?: string;
  userName?: string;
  className?: string;
}

export const PrList: React.FC<PrListProps> = ({
  clientId,
  showMlFields = false,
  limit = 50,
  repository,
  status,
  userName,
  className = '',
}) => {
  const [prsResponse, setPrsResponse] = useState<PrsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchPrs = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await apiService.getPrs(clientId, {
          limit,
          include_ml_fields: showMlFields,
          repository,
          status,
          user_name: userName,
        });

        setPrsResponse(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch pull requests');
      } finally {
        setLoading(false);
      }
    };

    fetchPrs();
  }, [clientId, showMlFields, limit, repository, status, userName]);

  if (loading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-green-600"></div>
        <span className="ml-2 text-secondary">Loading pull requests...</span>
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
            <h3 className="text-sm font-medium text-red-800">Error loading pull requests</h3>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!prsResponse || prsResponse.pull_requests.length === 0) {
    return (
      <div className={`text-center p-8 ${className}`}>
        <div className="text-secondary">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 7v8a2 2 0 002 2h6M8 7V5a2 2 0 012-2h4.586a1 1 0 01.707.293l4.414 4.414a1 1 0 01.293.707V15a2 2 0 01-2 2v0a2 2 0 01-2-2v-2a2 2 0 00-2-2H8z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-secondary">No pull requests found</h3>
          <p className="mt-1 text-sm text-tertiary">Try adjusting your filters or check back later.</p>
        </div>
      </div>
    );
  }

  const getStatusColor = (status?: string) => {
    switch (status?.toLowerCase()) {
      case 'merged':
        return 'bg-purple-100 text-purple-800';
      case 'open':
        return 'bg-green-100 text-green-800';
      case 'closed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getRiskLevelColor = (riskLevel?: string) => {
    switch (riskLevel?.toLowerCase()) {
      case 'high':
        return 'bg-red-100 text-red-800';
      case 'medium':
        return 'bg-yellow-100 text-yellow-800';
      case 'low':
        return 'bg-green-100 text-green-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  return (
    <div className={`space-y-4 ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-2">
          <h2 className="text-lg font-semibold text-primary">
            Pull Requests ({prsResponse.total_count})
          </h2>
          {prsResponse.ml_fields_included && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-green-100 text-green-800">
              ML Enhanced
            </span>
          )}
        </div>
        {prsResponse.count < prsResponse.total_count && (
          <span className="text-sm text-tertiary">
            Showing {prsResponse.count} of {prsResponse.total_count}
          </span>
        )}
      </div>

      {/* Pull Requests List */}
      <div className="space-y-3">
        {prsResponse.pull_requests.map((pr, index) => (
          <motion.div
            key={pr.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            className="bg-card border border-border rounded-lg p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div className="flex-1 min-w-0">
                {/* PR Header */}
                <div className="flex items-center space-x-2 mb-2">
                  <h3 className="text-sm font-medium text-primary truncate">
                    #{pr.number}: {pr.name}
                  </h3>
                  <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getStatusColor(pr.status)}`}>
                    {pr.status || 'Unknown'}
                  </span>
                </div>

                {/* PR Details */}
                <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm text-secondary">
                  {pr.user_name && (
                    <div>
                      <span className="font-medium">Author:</span> {pr.user_name}
                    </div>
                  )}
                  {pr.commit_count && (
                    <div>
                      <span className="font-medium">Commits:</span> {pr.commit_count}
                    </div>
                  )}
                  {pr.changed_files && (
                    <div>
                      <span className="font-medium">Files:</span> {pr.changed_files}
                    </div>
                  )}
                  {pr.review_cycles && (
                    <div>
                      <span className="font-medium">Review Cycles:</span> {pr.review_cycles}
                    </div>
                  )}
                </div>

                {/* Code Changes */}
                {(pr.additions || pr.deletions) && (
                  <div className="mt-2 flex items-center space-x-4 text-sm">
                    {pr.additions && (
                      <span className="text-green-600">
                        +{pr.additions} additions
                      </span>
                    )}
                    {pr.deletions && (
                      <span className="text-red-600">
                        -{pr.deletions} deletions
                      </span>
                    )}
                  </div>
                )}

                {/* Description */}
                {pr.body && (
                  <p className="mt-2 text-sm text-tertiary line-clamp-2">
                    {pr.body}
                  </p>
                )}

                {/* ML Fields - Only show if enabled and data exists */}
                {showMlFields && (pr.ml_rework_probability || pr.ml_risk_level || pr.embedding) && (
                  <div className="mt-3 p-3 bg-green-50 border border-green-200 rounded-md">
                    <h4 className="text-xs font-medium text-green-800 mb-2">ML Insights</h4>
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 text-xs text-green-700">
                      {pr.ml_rework_probability && (
                        <div>
                          <span className="font-medium">Rework Probability:</span> {(pr.ml_rework_probability * 100).toFixed(1)}%
                        </div>
                      )}
                      {pr.ml_risk_level && (
                        <div className="flex items-center space-x-1">
                          <span className="font-medium">Risk Level:</span>
                          <span className={`inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${getRiskLevelColor(pr.ml_risk_level)}`}>
                            {pr.ml_risk_level}
                          </span>
                        </div>
                      )}
                      {pr.embedding && (
                        <div>
                          <span className="font-medium">Vector Embedding:</span> Available ({pr.embedding.length} dimensions)
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>

              {/* PR Actions */}
              <div className="flex items-center space-x-2 ml-4">
                {pr.url && (
                  <button
                    onClick={() => window.open(pr.url, '_blank')}
                    className="text-green-600 hover:text-green-800 text-sm font-medium"
                  >
                    View
                  </button>
                )}
              </div>
            </div>

            {/* Timestamps */}
            <div className="mt-3 pt-3 border-t border-border flex justify-between text-xs text-tertiary">
              <span>Created: {pr.pr_created_at ? new Date(pr.pr_created_at).toLocaleDateString() : 'Unknown'}</span>
              {pr.merged_at && (
                <span>Merged: {new Date(pr.merged_at).toLocaleDateString()}</span>
              )}
              {!pr.merged_at && pr.pr_updated_at && (
                <span>Updated: {new Date(pr.pr_updated_at).toLocaleDateString()}</span>
              )}
            </div>
          </motion.div>
        ))}
      </div>

      {/* Load More Button */}
      {prsResponse.count < prsResponse.total_count && (
        <div className="text-center pt-4">
          <button className="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 transition-colors">
            Load More Pull Requests
          </button>
        </div>
      )}
    </div>
  );
};

export default PrList;
