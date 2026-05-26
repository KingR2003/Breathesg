import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_URL || '/api'

const api = axios.create({
  baseURL: API_BASE,
  headers: { 'Content-Type': 'application/json' },
})

// Attach auth token from localStorage
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token')
  if (token) config.headers.Authorization = `Token ${token}`
  return config
})

// On 401, clear token and reload
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('auth_token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api

// ── Auth ────────────────────────────────────────────────────────
export const authAPI = {
  login: (username, password) => api.post('/auth/login/', { username, password }),
  logout: () => api.post('/auth/logout/'),
  me: () => api.get('/auth/me/'),
}

// ── Ingest ──────────────────────────────────────────────────────
export const ingestAPI = {
  uploadSAP: (file, tenantId) => {
    const fd = new FormData()
    fd.append('file', file)
    if (tenantId) fd.append('tenant_id', tenantId)
    return api.post('/ingest/sap/', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  uploadUtility: (file, tenantId) => {
    const fd = new FormData()
    fd.append('file', file)
    if (tenantId) fd.append('tenant_id', tenantId)
    return api.post('/ingest/utility/', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
  uploadTravel: (file, tenantId) => {
    const fd = new FormData()
    fd.append('file', file)
    if (tenantId) fd.append('tenant_id', tenantId)
    return api.post('/ingest/travel/', fd, { headers: { 'Content-Type': 'multipart/form-data' } })
  },
}

// ── Batches ──────────────────────────────────────────────────────
export const batchAPI = {
  list: (params) => api.get('/batches/', { params }),
}

// ── Records ──────────────────────────────────────────────────────
export const recordAPI = {
  list: (params) => api.get('/records/', { params }),
  get: (id) => api.get(`/records/${id}/`),
  update: (id, data) => api.patch(`/records/${id}/`, data),
  approve: (id, data) => api.post(`/records/${id}/approve/`, data),
  reject: (id, data) => api.post(`/records/${id}/reject/`, data),
  flag: (id, data) => api.post(`/records/${id}/flag/`, data),
  bulkAction: (ids, action, notes) => api.post('/records/bulk-action/', { ids, action, notes }),
  audit: (id) => api.get(`/records/${id}/audit/`),
}

// ── Summary ──────────────────────────────────────────────────────
export const summaryAPI = {
  get: (tenantId) => api.get('/summary/', { params: tenantId ? { tenant: tenantId } : {} }),
}

// ── Tenants ──────────────────────────────────────────────────────
export const tenantAPI = {
  list: () => api.get('/tenants/'),
}
