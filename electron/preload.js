'use strict'
// Minimal preload — all communication happens via HTTP to localhost:7531
// No IPC needed since the backend is a local HTTP server
const { contextBridge } = require('electron')

contextBridge.exposeInMainWorld('fmailApp', {
  version: process.env.npm_package_version || '7.3.1',
  platform: process.platform,
})
