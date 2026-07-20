import { contextBridge, ipcRenderer } from 'electron'

interface StorageQuota {
  totalBytes: number
  threshold: number
  exceeded: boolean
  root: string
}

const api = {
  getBackendUrl: (): Promise<string> => ipcRenderer.invoke('get-backend-url'),
  invoke: (channel: string, ...args: unknown[]): Promise<unknown> => {
    return ipcRenderer.invoke(channel, ...args)
  },
  getSettings: (): Promise<Record<string, unknown>> => ipcRenderer.invoke('get-settings'),
  saveSettings: (data: Record<string, unknown>): Promise<boolean> => ipcRenderer.invoke('save-settings', data),
  getStorageQuota: (): Promise<StorageQuota> => ipcRenderer.invoke('storage:quota'),
  revealInFolder: (fullPath: string): Promise<boolean> => ipcRenderer.invoke('storage:reveal', fullPath),
  onWindowState: (callback: (state: { isMaximized: boolean }) => void) => {
    const handler = (_event: any, state: { isMaximized: boolean }) => callback(state)
    ipcRenderer.on('window-state-changed', handler)
    return () => ipcRenderer.removeListener('window-state-changed', handler)
  }
}

contextBridge.exposeInMainWorld('electronAPI', api)
