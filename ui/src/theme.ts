/**
   * FMailSender Design System v6.0
   * Single source of truth for all design tokens.
   * Edit here → changes propagate everywhere.
   */

  export const colors = {
    base:    '#040410',
    surface: '#0d1117',
    surf2:   '#141424',
    surf3:   '#1c1c35',
    purple:  '#8b5cf6',
    purpleLight: '#a78bfa',
    cyan:    '#06b6d4',
    cyanLight: '#22d3ee',
    text:    '#e8e8ff',
    muted:   '#6666aa',
    dim:     '#3a3a66',
    success: '#10b981',
    error:   '#ef4444',
    warn:    '#f59e0b',
  } as const

  export type StatusType = 'ok' | 'error' | 'warn' | 'idle' | 'running' | 'paused' | 'done'

  export const statusColors: Record<StatusType, string> = {
    ok:      colors.success,
    error:   colors.error,
    warn:    colors.warn,
    idle:    colors.muted,
    running: colors.cyan,
    paused:  colors.warn,
    done:    colors.success,
  }

  export const statusLabels: Record<string, string> = {
    idle:    'Ожидание',
    running: 'Отправка',
    paused:  'Пауза',
    done:    'Завершено',
    error:   'Ошибка',
  }
  