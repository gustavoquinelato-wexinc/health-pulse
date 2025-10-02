import React, { useState } from 'react';

interface ReassignmentTarget {
  id: number;
  [key: string]: any;
}

interface DependencyModalProps {
  isOpen: boolean;
  onClose: () => void;
  onConfirm: (targetId?: number) => void;
  title: string;
  itemName: string;
  action: 'delete' | 'deactivate' | 'activate';
  dependencyCount: number;
  affectedItemsCount: number;
  dependencyType: string; // e.g., "work item type mapping(s)"
  affectedItemType: string; // e.g., "work item(s)"
  reassignmentTargets: ReassignmentTarget[];
  targetDisplayField: string; // field to display in dropdown
  allowSkipReassignment?: boolean; // for deactivation, can skip reassignment
  onShowError?: (title: string, message: string) => void; // toast function for errors
}

const DependencyModal: React.FC<DependencyModalProps> = ({
  isOpen,
  onClose,
  onConfirm,
  title,
  itemName,
  action,
  dependencyCount,
  affectedItemsCount,
  dependencyType,
  affectedItemType,
  reassignmentTargets,
  targetDisplayField,
  allowSkipReassignment = false,
  onShowError
}) => {
  const [selectedTargetId, setSelectedTargetId] = useState<number | undefined>(undefined);

  if (!isOpen) return null;

  const handleConfirm = () => {
    if (action === 'delete' && !selectedTargetId) {
      if (onShowError) {
        onShowError('Selection Required', 'Please select a target for reassignment before deleting.');
      } else {
        // Fallback to alert if no toast function provided
        alert('Please select a target for reassignment before deleting.');
      }
      return;
    }
    onConfirm(selectedTargetId);
  };

  const handleClose = () => {
    setSelectedTargetId(undefined);
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg shadow-xl max-w-md w-full mx-4">
        <div className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">
              {title}
            </h3>
            <button
              onClick={handleClose}
              className="text-gray-400 hover:text-gray-600"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>

          <div className="mb-4">
            <p className="text-sm text-gray-600 mb-2">
              You are about to {action} the item: <strong className="text-gray-900">{itemName}</strong>
            </p>
            
            <div className="bg-yellow-50 border border-yellow-200 rounded-md p-3 mb-4">
              <div className="flex">
                <svg className="w-5 h-5 text-yellow-400 mr-2 mt-0.5" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                <div>
                  <p className="text-sm text-yellow-800">
                    <strong>This item has dependencies:</strong>
                  </p>
                  <ul className="text-sm text-yellow-700 mt-1">
                    <li>• {dependencyCount} {dependencyType}</li>
                    <li>• {affectedItemsCount} {affectedItemType}</li>
                  </ul>
                </div>
              </div>
            </div>

            <div className="mb-4">
              <label htmlFor="reassignTarget" className="block text-sm font-medium text-gray-700 mb-2">
                {action === 'delete' ? 'Reassign to:' : 'Optionally reassign to:'}
                {action === 'delete' && <span className="text-red-500 ml-1">*</span>}
              </label>

              {/* Explanatory message above dropdown */}
              <p className="text-xs text-gray-600 mb-2">
                {allowSkipReassignment
                  ? 'Select a target to reassign dependent items to, or leave empty to keep all items unchanged.'
                  : 'Select a target to reassign all dependent items to before deletion.'
                }
              </p>

              <select
                id="reassignTarget"
                value={selectedTargetId || ''}
                onChange={(e) => setSelectedTargetId(e.target.value ? Number(e.target.value) : undefined)}
                className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              >
                <option value="">
                  {allowSkipReassignment ? 'Select target (optional)' : 'Select target'}
                </option>
                {reassignmentTargets.map((target) => (
                  <option key={target.id} value={target.id}>
                    {target[targetDisplayField]}
                  </option>
                ))}
              </select>
            </div>

            {action === 'delete' && (
              <p className="text-xs text-gray-500">
                * Reassignment is required for deletion. All dependent items will be moved to the selected target.
              </p>
            )}
            
            {action === 'deactivate' && allowSkipReassignment && (
              <p className="text-xs text-gray-500">
                Reassignment is optional for deactivation. If no target is selected, dependent items will remain unchanged.
              </p>
            )}
          </div>

          <div className="flex justify-end space-x-3">
            <button
              onClick={handleClose}
              className="px-4 py-2 text-sm font-medium text-gray-700 bg-gray-100 border border-gray-300 rounded-md hover:bg-gray-200 focus:outline-none focus:ring-2 focus:ring-gray-500"
            >
              Cancel
            </button>
            <button
              onClick={handleConfirm}
              className={`px-4 py-2 text-sm font-medium text-white rounded-md focus:outline-none focus:ring-2 ${
                action === 'delete'
                  ? 'bg-red-600 hover:bg-red-700 focus:ring-red-500'
                  : 'bg-yellow-600 hover:bg-yellow-700 focus:ring-yellow-500'
              }`}
            >
              {action === 'delete' ? 'Delete' : 'Deactivate'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DependencyModal;
