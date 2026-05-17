import { useCallback } from 'react'
import { useStore } from '../store'
import { createSession } from '@/api/os'

const useSessionLoader = () => {
  const selectedEndpoint = useStore((state) => state.selectedEndpoint)
  const setSessionId = useStore((state) => state.setSessionId)

  const createNewSession = useCallback(async () => {
    if (!selectedEndpoint) return null

    const newId = await createSession(selectedEndpoint)
    if (newId) {
      setSessionId(newId)
    }
    return newId
  }, [selectedEndpoint, setSessionId])

  return { createNewSession }
}

export default useSessionLoader
