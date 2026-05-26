import React from 'react'
import useToastStore from '../store/useToastStore'
import { CheckCircle, XCircle, X } from 'lucide-react'

export default function ToastContainer() {
  const { toasts, remove } = useToastStore()

  return (
    <div className="toast-container">
      {toasts.map((toast) => (
        <div key={toast.id} className={`toast toast-${toast.type}`}>
          {toast.type === 'success'
            ? <CheckCircle size={16} />
            : <XCircle size={16} />
          }
          <span>{toast.message}</span>
          <button
            onClick={() => remove(toast.id)}
            style={{ marginLeft: 'auto', background: 'none', border: 'none', cursor: 'pointer', color: 'inherit' }}
          >
            <X size={14} />
          </button>
        </div>
      ))}
    </div>
  )
}
