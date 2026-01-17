/**
 * PipelineProgress component - displays real-time agent pipeline progress.
 *
 * Shows status of each agent in the 5-agent pipeline with timing information.
 */

import { AgentProgress } from '../hooks/usePipeline';
import './PipelineProgress.css';

interface PipelineProgressProps {
  agentProgress: AgentProgress[];
  isRunning: boolean;
  isConnecting: boolean;
  error: string | null;
  pipelineDuration?: number;
}

const AGENT_LABELS: Record<string, string> = {
  topic_finder: 'Topic Finder',
  source_checker: 'Source Checker',
  adversarial_checker: 'Adversarial Checker',
  writing_agent: 'Writing Agent',
  publisher: 'Publisher',
};

export function PipelineProgress({
  agentProgress,
  isRunning,
  isConnecting,
  error,
  pipelineDuration,
}: PipelineProgressProps) {
  const getStatusIcon = (status: AgentProgress['status']) => {
    switch (status) {
      case 'pending':
        return '⏱️';
      case 'running':
        return '⚙️';
      case 'completed':
        return '✅';
      case 'failed':
        return '❌';
      default:
        return '❓';
    }
  };

  const getStatusClass = (status: AgentProgress['status']) => {
    return `agent-status agent-status--${status}`;
  };

  return (
    <div className="pipeline-progress">
      <div className="pipeline-progress__header">
        <h3>Pipeline Progress</h3>
        {isConnecting && <span className="pipeline-progress__status">Connecting...</span>}
        {isRunning && !isConnecting && <span className="pipeline-progress__status pipeline-progress__status--running">Running...</span>}
        {!isRunning && !isConnecting && pipelineDuration && (
          <span className="pipeline-progress__status pipeline-progress__status--completed">
            Completed in {pipelineDuration.toFixed(2)}s
          </span>
        )}
      </div>

      {error && (
        <div className="pipeline-progress__error">
          <strong>Error:</strong> {error}
        </div>
      )}

      <div className="pipeline-progress__agents">
        {agentProgress.map((agent) => (
          <div key={agent.agentName} className={getStatusClass(agent.status)}>
            <div className="agent-status__icon">{getStatusIcon(agent.status)}</div>
            <div className="agent-status__info">
              <div className="agent-status__name">
                {AGENT_LABELS[agent.agentName] || agent.agentName}
              </div>
              {agent.duration !== undefined && (
                <div className="agent-status__duration">{agent.duration.toFixed(2)}s</div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
