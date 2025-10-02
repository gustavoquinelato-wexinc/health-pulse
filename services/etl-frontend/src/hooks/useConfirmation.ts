import { useState, useCallback } from 'react';

interface ConfirmationOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  type?: 'danger' | 'warning' | 'info';
  icon?: React.ReactNode;
}

interface ConfirmationState extends ConfirmationOptions {
  isOpen: boolean;
  onConfirm: () => void;
}

export const useConfirmation = () => {
  const [confirmation, setConfirmation] = useState<ConfirmationState>({
    isOpen: false,
    title: '',
    message: '',
    onConfirm: () => {},
  });

  const showConfirmation = useCallback((
    options: ConfirmationOptions,
    onConfirm: () => void
  ): Promise<boolean> => {
    return new Promise((resolve) => {
      setConfirmation({
        ...options,
        isOpen: true,
        onConfirm: () => {
          setConfirmation(prev => ({ ...prev, isOpen: false }));
          onConfirm();
          resolve(true);
        },
      });
    });
  }, []);

  const hideConfirmation = useCallback(() => {
    setConfirmation(prev => ({ ...prev, isOpen: false }));
  }, []);

  // Convenience methods for common confirmation types
  const confirmDelete = useCallback((
    itemName: string,
    onConfirm: () => void,
    customMessage?: string
  ) => {
    return showConfirmation({
      title: 'Delete Confirmation',
      message: customMessage || `Are you sure you want to delete "${itemName}"? This action cannot be undone.`,
      confirmText: 'Delete',
      cancelText: 'Cancel',
      type: 'danger'
    }, onConfirm);
  }, [showConfirmation]);

  const confirmDeactivate = useCallback((
    itemName: string,
    onConfirm: () => void,
    customMessage?: string
  ) => {
    return showConfirmation({
      title: 'Deactivate Confirmation',
      message: customMessage || `Are you sure you want to deactivate "${itemName}"?`,
      confirmText: 'Deactivate',
      cancelText: 'Cancel',
      type: 'warning'
    }, onConfirm);
  }, [showConfirmation]);

  const confirmAction = useCallback((
    title: string,
    message: string,
    onConfirm: () => void,
    confirmText: string = 'Confirm'
  ) => {
    return showConfirmation({
      title,
      message,
      confirmText,
      cancelText: 'Cancel',
      type: 'info'
    }, onConfirm);
  }, [showConfirmation]);

  return {
    confirmation,
    showConfirmation,
    hideConfirmation,
    confirmDelete,
    confirmDeactivate,
    confirmAction,
  };
};
