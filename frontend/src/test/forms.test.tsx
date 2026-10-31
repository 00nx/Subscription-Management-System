import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { vi } from 'vitest'
import { ApiError } from '@/services/api'
import { authService } from '@/services/auth.service'
import { makeUser, renderApp } from './utils'

afterEach(() => vi.restoreAllMocks())

describe('login form', () => {
  test('renders and shows validation errors without calling the API', async () => {
    const login = vi.spyOn(authService, 'login')
    renderApp('/login')
    await userEvent.click(await screen.findByRole('button', { name: /log in/i }))
    expect(await screen.findByText('Email is required')).toBeInTheDocument()
    expect(screen.getByText('Password is required')).toBeInTheDocument()
    expect(login).not.toHaveBeenCalled()
  })

  test('successful login lands on the role home page', async () => {
    const login = vi.spyOn(authService, 'login').mockResolvedValue(makeUser('ADMIN'))
    renderApp('/login')
    await userEvent.type(await screen.findByLabelText('Email'), 'admin@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'whatever')
    await userEvent.click(screen.getByRole('button', { name: /log in/i }))
    expect(login).toHaveBeenCalledWith({ email: 'admin@example.com', password: 'whatever' })
    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument()
  })

  test('shows the server error message', async () => {
    vi.spyOn(authService, 'login').mockRejectedValue(new ApiError('Invalid email or password', 401))
    renderApp('/login')
    await userEvent.type(await screen.findByLabelText('Email'), 'a@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'x')
    await userEvent.click(screen.getByRole('button', { name: /log in/i }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Invalid email or password')
  })
})

describe('registration form', () => {
  test('enforces the password rules client-side', async () => {
    const register = vi.spyOn(authService, 'register')
    renderApp('/register')
    await userEvent.type(await screen.findByLabelText('Full name'), 'Ada')
    await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'weakpass')
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))
    expect(await screen.findByText(/more than 8 characters/i)).toBeInTheDocument()
    expect(register).not.toHaveBeenCalled()
  })

  test('submits valid data then goes to login', async () => {
    const register = vi.spyOn(authService, 'register').mockResolvedValue(makeUser('CUSTOMER'))
    renderApp('/register')
    await userEvent.type(await screen.findByLabelText('Full name'), 'Ada Lovelace')
    await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'Str0ng!Passw0rd')
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))
    await waitFor(() => expect(register).toHaveBeenCalledWith({ full_name: 'Ada Lovelace', email: 'ada@example.com', password: 'Str0ng!Passw0rd' }))
    expect(await screen.findByRole('button', { name: /log in/i })).toBeInTheDocument()
  })

  test('maps backend field errors onto the form', async () => {
    vi.spyOn(authService, 'register').mockRejectedValue(new ApiError('Validation failed', 422, { email: ['value is not a valid email address'] }))
    renderApp('/register')
    await userEvent.type(await screen.findByLabelText('Full name'), 'Ada')
    await userEvent.type(screen.getByLabelText('Email'), 'ada@example.com')
    await userEvent.type(screen.getByLabelText('Password'), 'Str0ng!Passw0rd')
    await userEvent.click(screen.getByRole('button', { name: /create account/i }))
    expect(await screen.findByText('value is not a valid email address')).toBeInTheDocument()
  })
})

test('forgot password form shows the generic confirmation', async () => {
  vi.spyOn(authService, 'requestPasswordReset').mockResolvedValue('If that email is registered, a reset link will be sent')
  renderApp('/forgot-password')
  await userEvent.type(await screen.findByLabelText('Email'), 'a@example.com')
  await userEvent.click(screen.getByRole('button', { name: /send reset link/i }))
  expect(await screen.findByRole('status')).toHaveTextContent(/reset link will be sent/)
})
