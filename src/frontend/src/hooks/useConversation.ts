/**
 * React hook for managing conversation history with sessionStorage persistence.
 *
 * Stores conversation messages in sessionStorage, survives page refresh,
 * clears on unmount or explicit clear.
 */

import { useState, useEffect, useCallback } from 'react';
import type { ChatMessage, ClaimCard, ContextualResponse } from '../types';

const STORAGE_KEY = 'thereceipts_conversation';

interface ConversationState {
  messages: ChatMessage[];
}

function loadFromStorage(): ChatMessage[] {
  try {
    const stored = sessionStorage.getItem(STORAGE_KEY);
    if (!stored) return [];

    const parsed: ConversationState = JSON.parse(stored);
    // Convert ISO timestamp strings back to Date objects
    return parsed.messages.map(msg => ({
      ...msg,
      timestamp: new Date(msg.timestamp),
    }));
  } catch (error) {
    console.error('[useConversation] Error loading from storage:', error);
    return [];
  }
}

function saveToStorage(messages: ChatMessage[]): void {
  try {
    const state: ConversationState = { messages };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
  } catch (error) {
    console.error('[useConversation] Error saving to storage:', error);
  }
}

export function useConversation() {
  const [messages, setMessages] = useState<ChatMessage[]>(() => loadFromStorage());

  // Persist to sessionStorage whenever messages change
  useEffect(() => {
    saveToStorage(messages);
  }, [messages]);

  const addMessage = useCallback((
    role: 'user' | 'assistant',
    content: string,
    claimCard?: ClaimCard,
    contextualResponse?: ContextualResponse
  ) => {
    const newMessage: ChatMessage = {
      role,
      content,
      claim_card: claimCard,
      contextual_response: contextualResponse,
      timestamp: new Date(),
    };

    setMessages(prev => [...prev, newMessage]);
  }, []);

  const clearConversation = useCallback(() => {
    setMessages([]);
    sessionStorage.removeItem(STORAGE_KEY);
  }, []);

  return {
    messages,
    addMessage,
    clearConversation,
  };
}
