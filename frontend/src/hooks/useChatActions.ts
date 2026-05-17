import { useCallback } from 'react'

import { useStore } from '../store'

import { type ChatMessage } from '@/types/os'
import { checkHealth } from '@/api/os'

const useChatActions = () => {
  const { chatInputRef } = useStore()
  const selectedEndpoint = useStore((state) => state.selectedEndpoint)
  const setMessages = useStore((state) => state.setMessages)
  const setIsBackendOnline = useStore((state) => state.setIsBackendOnline)

  const checkBackendHealth = useCallback(async () => {
    try {
      const isOnline = await checkHealth(selectedEndpoint)
      setIsBackendOnline(isOnline)
      return isOnline
    } catch {
      setIsBackendOnline(false)
      return false
    }
  }, [selectedEndpoint, setIsBackendOnline])

  const clearChat = useCallback(() => {
    setMessages([])
  }, [setMessages])

  const focusChatInput = useCallback(() => {
    setTimeout(() => {
      requestAnimationFrame(() => chatInputRef?.current?.focus())
    }, 0)
  }, [chatInputRef])

  const addMessage = useCallback(
    (message: ChatMessage) => {
      setMessages((prevMessages) => [...prevMessages, message])
    },
    [setMessages]
  )

  const initialize = useCallback(async () => {
    return checkBackendHealth()
  }, [checkBackendHealth])

  return {
    clearChat,
    addMessage,
    focusChatInput,
    initialize,
    checkBackendHealth,
  }
}

export default useChatActions
