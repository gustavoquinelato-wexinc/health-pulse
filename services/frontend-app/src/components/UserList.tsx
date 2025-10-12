/**
 * User List Component with ML fields support
 * Phase 1-6: Frontend Service Compatibility
 */

import React, { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { UsersResponse } from '../types';
import apiService from '../services/apiService';

interface UserListProps {
  clientId: number;
  showMlFields?: boolean;
  limit?: number;
  activeOnly?: boolean;
  search?: string;
  className?: string;
}

export const UserList: React.FC<UserListProps> = ({
  clientId,
  showMlFields = false,
  limit = 50,
  activeOnly = true,
  search,
  className = '',
}) => {
  const [usersResponse, setUsersResponse] = useState<UsersResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchUsers = async () => {
      try {
        setLoading(true);
        setError(null);

        const response = await apiService.getUsers(clientId, {
          limit,
          include_ml_fields: showMlFields,
          active_only: activeOnly,
          search,
        });

        setUsersResponse(response);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch users');
      } finally {
        setLoading(false);
      }
    };

    fetchUsers();
  }, [clientId, showMlFields, limit, activeOnly, search]);

  if (loading) {
    return (
      <div className={`flex items-center justify-center p-8 ${className}`}>
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-600"></div>
        <span className="ml-2 text-secondary">Loading users...</span>
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
            <h3 className="text-sm font-medium text-red-800">Error loading users</h3>
            <p className="text-sm text-red-700 mt-1">{error}</p>
          </div>
        </div>
      </div>
    );
  }

  if (!usersResponse || usersResponse.users.length === 0) {
    return (
      <div className={`text-center p-8 ${className}`}>
        <div className="text-secondary">
          <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197m13.5-9a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z" />
          </svg>
          <h3 className="mt-2 text-sm font-medium text-secondary">No users found</h3>
          <p className="mt-1 text-sm text-tertiary">Try adjusting your filters or check back later.</p>
        </div>
      </div>
    );
  }

  const getRoleColor = (role: string) => {
    switch (role.toLowerCase()) {
      case 'admin':
        return 'bg-red-100 text-red-800';
      case 'user':
        return 'bg-blue-100 text-blue-800';
      case 'viewer':
        return 'bg-gray-100 text-gray-800';
      default:
        return 'bg-gray-100 text-gray-800';
    }
  };

  const getAccessibilityLevel = (level: string) => {
    switch (level.toLowerCase()) {
      case 'aaa':
        return 'bg-green-100 text-green-800';
      case 'aa':
        return 'bg-yellow-100 text-yellow-800';
      case 'regular':
        return 'bg-gray-100 text-gray-800';
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
            Users ({usersResponse.total_count})
          </h2>
          {usersResponse.ml_fields_included && (
            <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-purple-100 text-purple-800">
              ML Enhanced
            </span>
          )}
        </div>
        {usersResponse.count < usersResponse.total_count && (
          <span className="text-sm text-tertiary">
            Showing {usersResponse.count} of {usersResponse.total_count}
          </span>
        )}
      </div>

      {/* Users List */}
      <div className="space-y-3">
        {usersResponse.users.map((user, index) => (
          <motion.div
            key={user.id}
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3, delay: index * 0.05 }}
            className="bg-card border border-border rounded-lg p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center space-x-4">
                {/* User Avatar */}
                <div className="flex-shrink-0">
                  {user.profile_image_filename ? (
                    <img
                      className="h-10 w-10 rounded-full"
                      src={`/api/v1/users/${user.id}/profile-image`}
                      alt={`${user.first_name} ${user.last_name}`}
                    />
                  ) : (
                    <div className="h-10 w-10 rounded-full bg-gray-300 flex items-center justify-center">
                      <span className="text-sm font-medium text-gray-700">
                        {user.first_name?.[0]}{user.last_name?.[0]}
                      </span>
                    </div>
                  )}
                </div>

                {/* User Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center space-x-2 mb-1">
                    <h3 className="text-sm font-medium text-primary truncate">
                      {user.first_name} {user.last_name}
                    </h3>
                    <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${getRoleColor(user.role)}`}>
                      {user.role}
                    </span>
                    {user.is_admin && (
                      <span className="inline-flex items-center px-2 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                        Admin
                      </span>
                    )}
                  </div>

                  <p className="text-sm text-secondary">{user.email}</p>

                  {/* User Details */}
                  <div className="mt-2 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs text-tertiary">
                    <div>
                      <span className="font-medium">Auth:</span> {user.auth_provider}
                    </div>
                    <div>
                      <span className="font-medium">Theme:</span> {user.theme_mode}
                    </div>
                    <div>
                      <span className="font-medium">Accessibility:</span>
                      <span className={`ml-1 inline-flex items-center px-1.5 py-0.5 rounded text-xs font-medium ${getAccessibilityLevel(user.accessibility_level)}`}>
                        {user.accessibility_level.toUpperCase()}
                      </span>
                    </div>
                    {user.last_login_at && (
                      <div>
                        <span className="font-medium">Last Login:</span> {new Date(user.last_login_at).toLocaleDateString()}
                      </div>
                    )}
                  </div>

                  {/* Accessibility Features */}
                  {(user.high_contrast_mode || user.reduce_motion || user.colorblind_safe_palette) && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {user.high_contrast_mode && (
                        <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-blue-100 text-blue-800">
                          High Contrast
                        </span>
                      )}
                      {user.reduce_motion && (
                        <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-green-100 text-green-800">
                          Reduced Motion
                        </span>
                      )}
                      {user.colorblind_safe_palette && (
                        <span className="inline-flex items-center px-2 py-1 rounded text-xs bg-yellow-100 text-yellow-800">
                          Colorblind Safe
                        </span>
                      )}
                    </div>
                  )}

                  {/* ML Fields - Only show if enabled and data exists */}
                  {showMlFields && user.embedding && (
                    <div className="mt-3 p-3 bg-purple-50 border border-purple-200 rounded-md">
                      <h4 className="text-xs font-medium text-purple-800 mb-2">ML Insights</h4>
                      <div className="text-xs text-purple-700">
                        <span className="font-medium">Vector Embedding:</span> Available ({user.embedding.length} dimensions)
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* User Actions */}
              <div className="flex items-center space-x-2 ml-4">
                <button
                  onClick={() => window.open(`/users/${user.id}`, '_blank')}
                  className="text-purple-600 hover:text-purple-800 text-sm font-medium"
                >
                  View
                </button>
              </div>
            </div>

            {/* Timestamps */}
            <div className="mt-3 pt-3 border-t border-border flex justify-between text-xs text-tertiary">
              <span>Created: {new Date(user.created_at).toLocaleDateString()}</span>
              <span>Updated: {new Date(user.last_updated_at).toLocaleDateString()}</span>
            </div>
          </motion.div>
        ))}
      </div>

      {/* Load More Button */}
      {usersResponse.count < usersResponse.total_count && (
        <div className="text-center pt-4">
          <button className="px-4 py-2 bg-purple-600 text-white rounded-md hover:bg-purple-700 transition-colors">
            Load More Users
          </button>
        </div>
      )}
    </div>
  );
};

export default UserList;
