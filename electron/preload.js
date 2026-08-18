'use strict'
// Minimal preload — all communication happens via HTTP to localhost:7531
// No IPC needed since the backend is a local HTTP server
const { contextBridge, ipcRenderer } = require('electron')

contextBridge.exposeInMainWorld('fmailApp', {
  version: process.env.npm_package_version || '7.5.7',
  platform: process.platform,
  restartApp: () => ipcRenderer.invoke('app:restart'),
  setCloseWarningEnabled: (enabled) => ipcRenderer.invoke('app:set-close-warning', Boolean(enabled)),
})
