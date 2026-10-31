import type { AppNotification, AuditLog, EmailLog, Dashboard, Page, PageParams, ReportResult, User } from '@/types'
import { download, get, patch, post } from './http'

type P = PageParams & Record<string, string | number | boolean | undefined>

export const userService = {
  list: (p?: P) => get<Page<User>>('/users/', p),
  create: (b: unknown) => post<User>('/users/', b),
  update: (id: string, b: unknown) => patch<User>(`/users/${id}/`, b),
}
export const notificationService = {
  list: (p?: P) => get<Page<AppNotification>>('/notifications/', p),
  unread: () => get<{ count: number }>('/notifications/unread-count/'),
  read: (id: string) => post<AppNotification>(`/notifications/${id}/read/`),
  readAll: () => post<null>('/notifications/read-all/'),
}
export const emailService = {
  list: (p?: P) => get<Page<EmailLog>>('/email-logs/', p),
  summary: () => get<{ queued: number; sent: number; failed: number; suppressed: number }>('/email-logs/summary/'),
  retry: (id: string) => post<EmailLog>(`/email-logs/${id}/retry/`),
}
export const auditService = { list: (p?: P) => get<Page<AuditLog>>('/audit-logs/', p) }
export const analyticsService = { dashboard: (p?: P) => get<Dashboard>('/analytics/dashboard/', p) }
export const reportService = {
  get: (name: string, p?: P) => get<ReportResult>(`/reports/${name}/`, p),
  csv: (name: string, p?: P) => download(`/reports/${name}/`, { ...p, format: 'csv' }, `${name}-report.csv`),
  pdf: (name: string, p?: P) => download(`/reports/${name}/`, { ...p, format: 'pdf' }, `${name}-report.pdf`),
}
