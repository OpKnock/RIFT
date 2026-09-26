import { forwardRef, ButtonHTMLAttributes } from 'react'
import { cn } from '@/utils/cn'
import { useState, useEffect, useRef } from 'react'
import { ChevronDown } from 'lucide-react'

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'outline' | 'ghost' | 'destructive'
  size?: 'sm' | 'md' | 'lg'
  loading?: boolean
  icon?: React.ReactNode
  iconPosition?: 'left' | 'right'
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant = 'primary', size = 'md', loading, icon, iconPosition = 'left', disabled, children, ...props }, ref) => {
    const baseStyles = 'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed'

    const variants = {
      primary: 'bg-primary-600 text-white hover:bg-primary-700 active:bg-primary-800 focus-visible:ring-primary-500',
      secondary: 'bg-secondary-100 text-secondary-900 hover:bg-secondary-200 active:bg-secondary-300 focus-visible:ring-secondary-500 dark:bg-secondary-800 dark:text-secondary-100 dark:hover:bg-secondary-700 dark:active:bg-secondary-600',
      outline: 'border border-secondary-300 bg-transparent hover:bg-secondary-100 active:bg-secondary-200 focus-visible:ring-secondary-500 dark:border-secondary-600 dark:hover:bg-secondary-800 dark:active:bg-secondary-700',
      ghost: 'bg-transparent hover:bg-secondary-100 active:bg-secondary-200 focus-visible:ring-secondary-500 dark:hover:bg-secondary-800 dark:active:bg-secondary-700',
      destructive: 'bg-error-600 text-white hover:bg-error-700 active:bg-error-800 focus-visible:ring-error-500',
    }

    const sizes = {
      sm: 'px-3 py-1.5 text-xs gap-1.5',
      md: 'px-4 py-2 text-sm gap-2',
      lg: 'px-6 py-3 text-base gap-2',
    }

    return (
      <button
        ref={ref}
        className={cn(baseStyles, variants[variant], sizes[size], className)}
        disabled={disabled || loading}
        {...props}
      >
        {loading && (
          <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" aria-hidden="true">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
        )}
        {!loading && icon && iconPosition === 'left' && <span className="flex-shrink-0">{icon}</span>}
        <span>{children}</span>
        {!loading && icon && iconPosition === 'right' && <span className="flex-shrink-0">{icon}</span>}
      </button>
    )
  }
)

Button.displayName = 'Button'

export interface ButtonGroupProps {
  children: React.ReactNode
  className?: string
  vertical?: boolean
}

export function ButtonGroup({ children, className, vertical }: ButtonGroupProps) {
  return (
    <div
      className={cn(
        'inline-flex',
        vertical ? 'flex-col' : 'flex-row',
        className
      )}
      role="group"
      aria-label="Button group"
    >
      {children}
    </div>
  )
}

export interface IconButtonProps extends Omit<ButtonProps, 'children'> {
  'aria-label': string
  children: React.ReactNode
}

export function IconButton({ className, size = 'md', ...props }: IconButtonProps) {
  return (
    <Button
      variant="ghost"
      size={size}
      className={cn('p-0', size === 'sm' && 'w-8 h-8', size === 'md' && 'w-9 h-9', size === 'lg' && 'w-10 h-10', className)}
      {...props}
    />
  )
}

export interface SplitButtonProps {
  label: string
  onClick: () => void
  dropdownItems: Array<{
    label: string
    onClick: () => void
    icon?: React.ReactNode
    dangerous?: boolean
  }>
  variant?: 'primary' | 'secondary' | 'outline'
  size?: 'sm' | 'md' | 'lg'
  disabled?: boolean
  icon?: React.ReactNode
}

export function SplitButton({ label, onClick, dropdownItems, variant = 'primary', size = 'md', disabled, icon }: SplitButtonProps) {
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (ref.current && !ref.current.contains(event.target as Node)) {
        setOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <div ref={ref} className="relative inline-flex" role="group" aria-label="Split button">
      <Button variant={variant} size={size} disabled={disabled} onClick={onClick}>
        {icon && <span className="flex-shrink-0">{icon}</span>}
        {label}
      </Button>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        disabled={disabled}
        className={cn(
          'relative inline-flex items-center px-2 rounded-r-lg',
          'bg-inherit text-inherit hover:bg-secondary-100 dark:hover:bg-secondary-800',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2 focus-visible:ring-primary-500',
          'disabled:opacity-50 disabled:cursor-not-allowed'
        )}
        aria-haspopup="true"
        aria-expanded={open}
        aria-label="Toggle dropdown"
      >
        <ChevronDown className="w-4 h-4" aria-hidden="true" />
      </button>

      {open && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setOpen(false)} aria-hidden="true" />
          <div className="absolute right-0 z-50 mt-1 min-w-[160px] rounded-lg border border-secondary-200 bg-white py-1 shadow-lg dark:border-secondary-700 dark:bg-secondary-900 animate-fade-in">
            {dropdownItems.map((item, index) => (
              <button
                key={index}
                onClick={() => {
                  item.onClick()
                  setOpen(false)
                }}
                className={cn(
                  'flex items-center gap-2 w-full px-3 py-2 text-sm text-left text-secondary-700',
                  'hover:bg-secondary-100 dark:hover:bg-secondary-800',
                  'transition-colors',
                  item.dangerous && 'text-error-600 hover:bg-error-50 dark:text-error-400 dark:hover:bg-error-900/30'
                )}
                role="menuitem"
              >
                {item.icon && <span className="w-4 h-4 flex-shrink-0">{item.icon}</span>}
                {item.label}
              </button>
            ))}
          </div>
        </>
      )}
    </div>
  )
}