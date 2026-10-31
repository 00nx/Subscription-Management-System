import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { authService } from '@/services/auth.service'
import { renderApp } from './utils'

afterEach(() => vi.restoreAllMocks())

describe('protected routes', () => {
  test('anonymous users are sent to /login', async () => {
    renderApp('/dashboard', null)
    expect(await screen.findByRole('button', { name: /log in/i })).toBeInTheDocument()
  })

  test('customers cannot open admin pages', async () => {
    renderApp('/dashboard', 'CUSTOMER')
    expect(await screen.findByRole('heading', { name: 'Unauthorized' })).toBeInTheDocument()
  })

  test('admins cannot open customer pages', async () => {
    renderApp('/customer/dashboard', 'ADMIN')
    expect(await screen.findByRole('heading', { name: 'Unauthorized' })).toBeInTheDocument()
  })

  test('staff cannot open admin-only settings', async () => {
    renderApp('/settings', 'STAFF')
    expect(await screen.findByRole('heading', { name: 'Unauthorized' })).toBeInTheDocument()
  })

  test('logged-in users are redirected away from /login', async () => {
    renderApp('/login', 'CUSTOMER')
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  test('unknown paths show the not-found page', async () => {
    renderApp('/nope', 'ADMIN')
    expect(await screen.findByRole('heading', { name: 'Page not found' })).toBeInTheDocument()
  })
})

test('logging out returns to the login page and drops protected access', async () => {
  const logout = vi.spyOn(authService, 'logout').mockResolvedValue()
  renderApp('/dashboard', 'ADMIN')
  await userEvent.click(await screen.findByRole('button', { name: /log out/i }))
  expect(await screen.findByRole('button', { name: /log in/i })).toBeInTheDocument()
  expect(logout).toHaveBeenCalled()
  expect(screen.queryByRole('navigation', { name: 'Main' })).not.toBeInTheDocument()
})

describe('navigation', () => {
  test('admin sidebar links navigate and breadcrumbs follow', async () => {
    renderApp('/dashboard', 'ADMIN')
    await userEvent.click(await screen.findByRole('link', { name: 'Invoices' }))
    expect(await screen.findByRole('heading', { name: 'Invoices' })).toBeInTheDocument()
    expect(screen.getByRole('navigation', { name: 'Breadcrumb' })).toHaveTextContent('Invoices')
    expect(screen.getByText('No invoices yet')).toBeInTheDocument()
    expect(document.title).toBe('Invoices · Brightloop')
  })

  test('customers only see customer navigation', async () => {
    renderApp('/customer/dashboard', 'CUSTOMER')
    const nav = await screen.findByRole('navigation', { name: 'Main' })
    expect(nav).toHaveTextContent('Profile')
    expect(nav).not.toHaveTextContent('Products')
  })

  test('every admin placeholder route renders its title', async () => {
    for (const [path, title] of [['/products', 'Products'], ['/products/new', 'New product'], ['/products/abc', 'Product details'], ['/plans', 'Plans'], ['/subscriptions', 'Subscriptions'], ['/subscriptions/abc', 'Subscription details'], ['/quotations', 'Quotations'], ['/payments', 'Payments'], ['/discounts', 'Discounts'], ['/reports', 'Reports'], ['/settings', 'Settings']]) {
      const { unmount } = renderApp(path, 'ADMIN')
      expect(await screen.findByRole('heading', { name: title })).toBeInTheDocument()
      unmount()
    }
  })

  test('every customer placeholder route renders its title', async () => {
    for (const [path, title] of [['/customer/subscriptions', 'My subscriptions'], ['/customer/invoices', 'My invoices'], ['/customer/profile', 'Profile']]) {
      const { unmount } = renderApp(path, 'CUSTOMER')
      expect(await screen.findByRole('heading', { name: title })).toBeInTheDocument()
      unmount()
    }
  })
})
