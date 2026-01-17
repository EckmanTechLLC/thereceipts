/**
 * Ask page - Conversational chat interface.
 *
 * Full-width chat UI with message thread and real-time pipeline progress.
 */

import { useState, useRef, useEffect } from 'react';
import { useConversation } from '../hooks/useConversation';
import { usePipeline } from '../hooks/usePipeline';
import { api } from '../services/api';
import { MessageBubble } from '../components/chat/MessageBubble';
import { ClaimCardMessage } from '../components/chat/ClaimCardMessage';
import './AskPage.css';

const MAX_MESSAGE_LENGTH = 2000;

// Agent display configuration
const AGENT_DISPLAY_INFO: Record<string, { name: string; description: string }> = {
  topic_finder: {
    name: 'TopicFinder',
    description: 'Identifying core claim and context'
  },
  source_checker: {
    name: 'SourceChecker',
    description: 'Finding academic sources'
  },
  adversarial_checker: {
    name: 'Adversarial',
    description: 'Evaluating counterarguments'
  },
  writing_agent: {
    name: 'Writer',
    description: 'Composing response'
  },
  publisher: {
    name: 'Publisher',
    description: 'Finalizing claim card'
  }
};

const getAgentDisplayName = (agentId: string): string => {
  return AGENT_DISPLAY_INFO[agentId]?.name || agentId;
};

const getAgentDescription = (agentId: string): string => {
  return AGENT_DISPLAY_INFO[agentId]?.description || '';
};

const AGENT_ORDER = ['topic_finder', 'source_checker', 'adversarial_checker', 'writing_agent', 'publisher'];

interface LocalAgentProgress {
  agentName: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
}

export function AskPage() {
  const [inputValue, setInputValue] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isPipelineRunning, setIsPipelineRunning] = useState(false);
  const [routingPhase, setRoutingPhase] = useState<'analyzing' | 'routing' | 'done' | null>(null);
  const [agentProgress, setAgentProgress] = useState<LocalAgentProgress[]>(
    AGENT_ORDER.map(name => ({ agentName: name, status: 'pending' }))
  );
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const { messages, addMessage, clearConversation } = useConversation();
  const pipeline = usePipeline();

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, agentProgress]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Esc to clear input or dismiss error
      if (e.key === 'Escape') {
        if (error) {
          setError(null);
        } else if (inputValue) {
          setInputValue('');
        }
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [error, inputValue]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim() || isProcessing) return;

    const userMessage = inputValue.trim();

    // Validate message length
    if (userMessage.length > MAX_MESSAGE_LENGTH) {
      setError(`Message too long. Maximum ${MAX_MESSAGE_LENGTH} characters allowed.`);
      return;
    }

    // Clear any previous errors
    setError(null);
    setInputValue('');
    setIsProcessing(true);

    // Add user message to conversation
    addMessage('user', userMessage);

    try {
      // Call chat API with conversation history
      const response = await api.sendChatMessage(userMessage, messages);

      // Handle based on mode
      if (response.mode === 'EXACT_MATCH') {
        // Mode 1: Existing claim card found - add immediately
        const exactMatch = response.response as any;
        if (exactMatch.claim_card) {
          addMessage('assistant', '', exactMatch.claim_card);
        }
        setIsProcessing(false);
        setRoutingPhase(null);
      } else if (response.mode === 'CONTEXTUAL') {
        // Mode 2: Contextual response with source cards
        const contextual = response.response as any;
        addMessage('assistant', '', undefined, {
          synthesized_response: contextual.synthesized_response,
          source_cards: contextual.source_cards,
        });
        setIsProcessing(false);
        setRoutingPhase(null);
      } else if (response.mode === 'NOVEL_CLAIM') {
        // Mode 3: Pipeline is running in background - connect to WebSocket for updates
        const novelClaim = response.response as any;
        if (novelClaim.websocket_session_id) {
          // Reset and start pipeline progress tracking
          setIsPipelineRunning(true);
          setRoutingPhase(null);
          setAgentProgress(AGENT_ORDER.map(name => ({ agentName: name, status: 'pending' })));

          // Connect to WebSocket
          const ws = new WebSocket(`ws://${window.location.hostname}:8008/ws/pipeline/${novelClaim.websocket_session_id}`);

          ws.onmessage = (event) => {
            const data = JSON.parse(event.data);

            // Routing events
            if (data.type === 'context_analysis_started') {
              setRoutingPhase('analyzing');
            } else if (data.type === 'routing_started') {
              setRoutingPhase('routing');
            } else if (data.type === 'routing_completed') {
              setRoutingPhase('done');
            } else if (data.type === 'router_fallback') {
              console.warn('[AskPage] Router fallback:', data.reason);
            }
            // Pipeline agent events
            else if (data.type === 'agent_started') {
              // Update agent status to running
              setAgentProgress(prev =>
                prev.map(agent =>
                  agent.agentName === data.agent_name
                    ? { ...agent, status: 'running' }
                    : agent
                )
              );
            } else if (data.type === 'agent_completed') {
              // Update agent status to completed/failed
              setAgentProgress(prev =>
                prev.map(agent =>
                  agent.agentName === data.agent_name
                    ? { ...agent, status: data.success ? 'completed' : 'failed' }
                    : agent
                )
              );
            } else if (data.type === 'claim_card_ready') {
              // Pipeline complete - add claim card to conversation
              addMessage('assistant', '', data.claim_card);
              setIsProcessing(false);
              setIsPipelineRunning(false);
              setRoutingPhase(null);
              ws.close();
            } else if (data.type === 'pipeline_failed') {
              setError(data.error || 'Pipeline failed');
              setIsProcessing(false);
              setIsPipelineRunning(false);
              setRoutingPhase(null);
              ws.close();
            }
          };

          ws.onerror = (error) => {
            console.error('[AskPage] WebSocket error:', error);
            setError('Connection error. Please try again.');
            setIsProcessing(false);
            setIsPipelineRunning(false);
            setRoutingPhase(null);
          };

          ws.onclose = () => {
            console.log('[AskPage] WebSocket closed');
          };
        } else {
          setError('No WebSocket session ID received');
          setIsProcessing(false);
        }
      }
    } catch (error) {
      console.error('[AskPage] Error:', error);
      const errorMessage = error instanceof Error ? error.message : 'Unable to process your request. Please try again.';
      setError(errorMessage);
      setIsProcessing(false);
      setRoutingPhase(null);
    }
  };

  const handleClearConversation = () => {
    if (confirm('Clear conversation history?')) {
      clearConversation();
      pipeline.reset();
      setIsPipelineRunning(false);
      setAgentProgress(AGENT_ORDER.map(name => ({ agentName: name, status: 'pending' })));
    }
  };

  return (
    <div className="ask-page-chat">
      {/* Header */}
      <div className="chat-header">
        <h1>Ask</h1>
        <button onClick={handleClearConversation} className="clear-button">
          Clear Conversation
        </button>
      </div>

      {/* Message thread */}
      <div className="message-thread">
        {messages.length === 0 && !isPipelineRunning && (
          <div className="empty-state">
            <h2>Ask anything about Christian apologetics claims</h2>
            <p>Example: "Did Matthew really write the Gospel of Matthew?"</p>
          </div>
        )}

        {messages.map((msg, idx) => (
          <div key={idx}>
            {msg.role === 'user' ? (
              <MessageBubble content={msg.content} timestamp={msg.timestamp} />
            ) : (
              <ClaimCardMessage
                content={msg.content}
                card={msg.claim_card}
                contextualResponse={msg.contextual_response}
                timestamp={msg.timestamp}
              />
            )}
          </div>
        ))}

        {/* Routing phase indicator */}
        {routingPhase && routingPhase !== 'done' && (
          <div className="routing-progress">
            <div className="progress-spinner"></div>
            <div className="progress-text">
              {routingPhase === 'analyzing' && 'Analyzing context...'}
              {routingPhase === 'routing' && 'Routing question...'}
            </div>
          </div>
        )}

        {/* Pipeline progress indicator */}
        {isPipelineRunning && (
          <div className="pipeline-progress">
            {(() => {
              const completedCount = agentProgress.filter(a => a.status === 'completed').length;
              const totalCount = agentProgress.length;
              const currentAgent = agentProgress.find(a => a.status === 'running');
              const currentIndex = currentAgent ? agentProgress.indexOf(currentAgent) + 1 : completedCount;
              const progressPercent = (completedCount / totalCount) * 100;

              return (
                <>
                  <div className="progress-header">
                    <div className="progress-spinner"></div>
                    <div className="progress-text">
                      <div className="progress-title">
                        {currentAgent ? (
                          <>
                            Agent {currentIndex} of {totalCount}: {getAgentDisplayName(currentAgent.agentName)}
                          </>
                        ) : (
                          <>Starting pipeline...</>
                        )}
                      </div>
                      {currentAgent && (
                        <div className="progress-subtitle">
                          {getAgentDescription(currentAgent.agentName)}
                        </div>
                      )}
                    </div>
                  </div>

                  {/* Visual progress bar */}
                  <div className="progress-bar-container">
                    <div className="progress-bar-fill" style={{ width: `${progressPercent}%` }}></div>
                  </div>

                  {/* Agent list */}
                  <div className="agent-progress-list">
                    {agentProgress.map((agent, idx) => (
                      <div key={idx} className={`agent-item agent-${agent.status}`}>
                        <span className="agent-name">{getAgentDisplayName(agent.agentName)}</span>
                        <span className="agent-status">{agent.status}</span>
                      </div>
                    ))}
                  </div>
                </>
              );
            })()}
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area */}
      <div className="chat-input-container">
        {error && (
          <div className="error-banner">
            <span className="error-icon">⚠</span>
            <span className="error-message">{error}</span>
            <button
              onClick={() => setError(null)}
              className="error-dismiss"
              aria-label="Dismiss error"
            >
              ✕
            </button>
          </div>
        )}
        <form onSubmit={handleSubmit} className="chat-input-form">
          <input
            type="text"
            placeholder="Ask a question..."
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            disabled={isProcessing}
            className="chat-input"
            maxLength={MAX_MESSAGE_LENGTH}
          />
          <button
            type="submit"
            disabled={!inputValue.trim() || isProcessing}
            className={`send-button ${isProcessing ? 'loading' : ''}`}
          >
            {isProcessing ? 'Sending...' : 'Send'}
          </button>
        </form>
        {inputValue.length > MAX_MESSAGE_LENGTH * 0.9 && (
          <div className="character-count">
            {inputValue.length} / {MAX_MESSAGE_LENGTH}
          </div>
        )}
      </div>
    </div>
  );
}
