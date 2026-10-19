// web/src/lib/fileStorage.ts
const DB_NAME = 'predicare_files'
const DB_VERSION = 1
const STORE = 'justificatifs'
const MAX_SIZE = 5 * 1024 * 1024

export interface StoredFile {
  id: string
  name: string
  type: string
  size: number
  dataUrl: string
  createdAt: string
}

let dbPromise: Promise<IDBDatabase> | null = null

function openDb(): Promise<IDBDatabase> {
  if (dbPromise) return dbPromise
  dbPromise = new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION)
    req.onupgradeneeded = () => {
      const db = req.result
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE, { keyPath: 'id' })
      }
    }
    req.onsuccess = () => resolve(req.result)
    req.onerror = () => reject(req.error)
  })
  return dbPromise
}

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

export async function saveFile(file: File): Promise<StoredFile> {
  if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
    throw new Error('Seuls les fichiers PDF sont acceptés.')
  }
  if (file.size > MAX_SIZE) {
    throw new Error(`Le fichier dépasse 5 Mo (${(file.size / 1024 / 1024).toFixed(1)} Mo).`)
  }
  const id = `JUST-${crypto.randomUUID()}`
  const dataUrl = await fileToDataUrl(file)
  const stored: StoredFile = {
    id,
    name: file.name,
    type: 'application/pdf',
    size: file.size,
    dataUrl,
    createdAt: new Date().toISOString(),
  }
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).put(stored)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
  return stored
}

export async function getFile(id: string): Promise<StoredFile | null> {
  const db = await openDb()
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly')
    const req = tx.objectStore(STORE).get(id)
    req.onsuccess = () => resolve((req.result as StoredFile | undefined) ?? null)
    req.onerror = () => reject(req.error)
  })
}

export async function deleteFile(id: string): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).delete(id)
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}

export async function clearAllFiles(): Promise<void> {
  const db = await openDb()
  await new Promise<void>((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite')
    tx.objectStore(STORE).clear()
    tx.oncomplete = () => resolve()
    tx.onerror = () => reject(tx.error)
  })
}