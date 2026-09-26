'use client'

import * as React from 'react'
import { forwardRef, HTMLAttributes } from 'react'
import { cn } from '@/utils/cn'

interface TabsContextValue {
  value: string
  onValueChange: (value: string) => void
  orientation: 'horizontal' | 'vertical'
}

const TabsContext = React.createContext<TabsContextValue | null>(null)

function useTabs() {
  const context = React.useContext(TabsContext)
  if (!context) {
    throw new Error('Tabs compound components must be used within Tabs')
  }
  return context
}

interface TabsProps {
  value: string
  onValueChange: (value: string) => void
  children: React.ReactNode
  className?: string
  defaultValue?: string
  orientation?: 'horizontal' | 'vertical'
}

export function Tabs({ value, onValueChange, children, className, orientation = 'horizontal' }: TabsProps) {
  return (
    <TabsContext.Provider value={{ value, onValueChange, orientation }}>
      <div
        className={cn(
          'flex',
          orientation === 'vertical' ? 'flex-col' : 'flex-row',
          className
        )}
        data-orientation={orientation}
      >
        {children}
      </div>
    </TabsContext.Provider>
  )
}

interface TabsListProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode
}

export const TabsList = forwardRef<HTMLDivElement, TabsListProps>(
  ({ className, children, ...props }, ref) => {
    const { orientation } = useTabs()
    return (
      <div
        ref={ref}
        role="tablist"
        aria-orientation={orientation}
        className={cn(
          'inline-flex items-center justify-center gap-1 p-1 bg-secondary-100 dark:bg-secondary-800 rounded-lg',
          orientation === 'vertical' ? 'flex-col w-auto' : 'flex-row',
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)

TabsList.displayName = 'TabsList'

interface TabsTriggerProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  value: string
  disabled?: boolean
}

export const TabsTrigger = forwardRef<HTMLButtonElement, TabsTriggerProps>(
  ({ className, value, disabled, children, ...props }, ref) => {
    const { value: selectedValue, onValueChange } = useTabs()

    return (
      <button
        ref={ref}
        role="tab"
        aria-selected={selectedValue === value}
        aria-disabled={disabled}
        data-state={selectedValue === value ? 'active' : 'inactive'}
        data-disabled={disabled ? '' : undefined}
        onClick={() => !disabled && onValueChange(value)}
        className={cn(
          'inline-flex items-center justify-center font-medium text-sm transition-all duration-200',
          'rounded-lg px-3 py-2',
          'focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2',
          'disabled:opacity-50 disabled:cursor-not-allowed',
          'data-[state=active]:bg-white dark:data-[state=active]:bg-secondary-900',
          'data-[state=active]:text-secondary-900 dark:data-[state=active]:text-white',
          'data-[state=inactive]:text-secondary-600 dark:data-[state=inactive]:text-secondary-400',
          'data-[state=inactive]:hover:bg-secondary-100 dark:data-[state=inactive]:hover:bg-secondary-800',
          className
        )}
        disabled={disabled}
        {...props}
      >
        {children}
      </button>
    )
  }
)

TabsTrigger.displayName = 'TabsTrigger'

interface TabsContentProps extends HTMLAttributes<HTMLDivElement> {
  value: string
  children: React.ReactNode
}

export const TabsContent = forwardRef<HTMLDivElement, TabsContentProps>(
  ({ className, value, children, ...props }, ref) => {
    const { value: contextValue } = useTabs()

    if (contextValue !== value) return null

    return (
      <div
        ref={ref}
        role="tabpanel"
        className={cn(
          'mt-2 ring-offset-white focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2',
          className
        )}
        {...props}
      >
        {children}
      </div>
    )
  }
)

TabsContent.displayName = 'TabsContent'