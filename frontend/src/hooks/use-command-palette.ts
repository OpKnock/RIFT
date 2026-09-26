import { create } from 'zustand'

interface CommandPaletteState {
  open: boolean
  openCommandPalette: () => void
  closeCommandPalette: () => void
  toggleCommandPalette: () => void
}

export const useCommandPalette = create<CommandPaletteState>((set) => ({
  open: false,
  openCommandPalette: () => set({ open: true }),
  closeCommandPalette: () => set({ open: false }),
  toggleCommandPalette: () => set((state) => ({ open: !state.open })),
}))