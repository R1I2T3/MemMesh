import { toast } from 'sonner'

import { APIRoutes } from './routes'

export const checkHealth = async (base: string): Promise<boolean> => {
  try {
    const response = await fetch(APIRoutes.Health(base), {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })
    return response.ok
  } catch {
    return false
  }
}

export const createSession = async (
  base: string,
): Promise<string | null> => {
  try {
    const response = await fetch(APIRoutes.NewSession(base), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
      toast.error(`Failed to create session: ${response.statusText}`)
      return null
    }
    const data = await response.json()
    return data.session_id
  } catch {
    toast.error('Error creating session')
    return null
  }
}

export const memorySearch = async (
  base: string,
  query: string,
): Promise<unknown[]> => {
  try {
    const url = `${APIRoutes.MemorySearch(base)}?query=${encodeURIComponent(query)}`
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
      return []
    }
    const data = await response.json()
    return data.results || []
  } catch {
    return []
  }
}

export const memoryGraph = async (
  base: string,
  entity: string,
): Promise<unknown[]> => {
  try {
    const url = `${APIRoutes.MemoryGraph(base)}?entity=${encodeURIComponent(entity)}`
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
    })
    if (!response.ok) {
      return []
    }
    const data = await response.json()
    return data.results || []
  } catch {
    return []
  }
}
