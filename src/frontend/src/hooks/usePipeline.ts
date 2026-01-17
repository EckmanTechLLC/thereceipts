/**
 * React hook for managing pipeline execution with real-time WebSocket updates.
 *
 * Handles WebSocket connection lifecycle, progress tracking, and API calls.
 */

import { useState, useEffect, useCallback, useRef } from 'react';
import { v4 as uuidv4 } from 'uuid';
import { PipelineWebSocketClient, ProgressEvent } from '../services/websocket';
import { api } from '../services/api';

export interface AgentProgress {
  agentName: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  startTime?: string;
  endTime?: string;
  duration?: number;
}

export interface PipelineState {
  isRunning: boolean;
  isConnecting: boolean;
  agentProgress: AgentProgress[];
  error: string | null;
  result: any | null;
  pipelineStartTime?: string;
  pipelineEndTime?: string;
  pipelineDuration?: number;
}

const AGENT_ORDER = ['topic_finder', 'source_checker', 'adversarial_checker', 'writing_agent', 'publisher'];

export function usePipeline() {
  const [state, setState] = useState<PipelineState>({
    isRunning: false,
    isConnecting: false,
    agentProgress: AGENT_ORDER.map(name => ({ agentName: name, status: 'pending' })),
    error: null,
    result: null,
  });

  const wsClientRef = useRef<PipelineWebSocketClient | null>(null);
  const sessionIdRef = useRef<string | null>(null);

  /**
   * Handle WebSocket progress events.
   */
  const handleProgressEvent = useCallback((event: ProgressEvent) => {
    setState(prev => {
      const newState = { ...prev };

      switch (event.type) {
        case 'pipeline_started':
          newState.pipelineStartTime = event.timestamp;
          newState.error = null;
          break;

        case 'agent_started':
          newState.agentProgress = prev.agentProgress.map(agent =>
            agent.agentName === event.agent_name
              ? { ...agent, status: 'running', startTime: event.timestamp }
              : agent
          );
          break;

        case 'agent_completed':
          newState.agentProgress = prev.agentProgress.map(agent =>
            agent.agentName === event.agent_name
              ? {
                  ...agent,
                  status: event.success ? 'completed' : 'failed',
                  endTime: event.timestamp,
                  duration: event.duration,
                }
              : agent
          );
          break;

        case 'pipeline_completed':
          newState.pipelineEndTime = event.timestamp;
          newState.pipelineDuration = event.duration;
          break;

        case 'pipeline_failed':
          newState.error = event.error;
          newState.pipelineEndTime = event.timestamp;
          newState.pipelineDuration = event.duration;
          newState.isRunning = false;
          break;

        case 'pong':
          // Heartbeat response, no state change needed
          break;

        default:
          console.warn('[usePipeline] Unknown event type:', event);
      }

      return newState;
    });
  }, []);

  /**
   * Run the pipeline with a question.
   */
  const runPipeline = useCallback(async (question: string) => {
    if (!question.trim()) {
      setState(prev => ({ ...prev, error: 'Question cannot be empty' }));
      return;
    }

    try {
      // Generate session ID
      const sessionId = uuidv4();
      sessionIdRef.current = sessionId;

      // Reset state
      setState({
        isRunning: true,
        isConnecting: true,
        agentProgress: AGENT_ORDER.map(name => ({ agentName: name, status: 'pending' })),
        error: null,
        result: null,
      });

      // Create and connect WebSocket
      const wsClient = new PipelineWebSocketClient(sessionId);
      wsClientRef.current = wsClient;
      wsClient.onProgress(handleProgressEvent);

      await wsClient.connect();

      setState(prev => ({ ...prev, isConnecting: false }));

      // Trigger pipeline execution via API
      const result = await api.runPipeline(question, sessionId);

      // Update final result
      setState(prev => ({
        ...prev,
        isRunning: false,
        result,
      }));

      // Close WebSocket connection
      wsClient.close();
      wsClientRef.current = null;
    } catch (error) {
      console.error('[usePipeline] Error:', error);
      setState(prev => ({
        ...prev,
        isRunning: false,
        isConnecting: false,
        error: error instanceof Error ? error.message : 'Unknown error occurred',
      }));

      // Clean up WebSocket on error
      if (wsClientRef.current) {
        wsClientRef.current.close();
        wsClientRef.current = null;
      }
    }
  }, [handleProgressEvent]);

  /**
   * Reset the pipeline state.
   */
  const reset = useCallback(() => {
    setState({
      isRunning: false,
      isConnecting: false,
      agentProgress: AGENT_ORDER.map(name => ({ agentName: name, status: 'pending' })),
      error: null,
      result: null,
    });
  }, []);

  /**
   * Clean up WebSocket on unmount.
   */
  useEffect(() => {
    return () => {
      if (wsClientRef.current) {
        wsClientRef.current.close();
        wsClientRef.current = null;
      }
    };
  }, []);

  return {
    ...state,
    runPipeline,
    reset,
  };
}
