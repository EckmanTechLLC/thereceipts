/**
 * Bot response message component with embedded claim card.
 *
 * Displays assistant messages as left-aligned with claim card content.
 * Supports Mode 1 (single claim card) and Mode 2 (contextual response with source cards).
 */

import { useState } from 'react';
import type { ClaimCard as ClaimCardType, ContextualResponse } from '../../types';
import { ClaimCard } from './ClaimCard';
import './ClaimCardMessage.css';

/**
 * Simple markdown renderer for contextual responses.
 * Handles headings, bold, lists, and links.
 */
function renderMarkdown(markdown: string): JSX.Element {
  const lines = markdown.split('\n');
  const elements: JSX.Element[] = [];
  let listItems: string[] = [];
  let inList = false;

  const flushList = () => {
    if (listItems.length > 0) {
      elements.push(
        <ul key={`list-${elements.length}`}>
          {listItems.map((item, i) => (
            <li key={i} dangerouslySetInnerHTML={{ __html: processInline(item) }} />
          ))}
        </ul>
      );
      listItems = [];
    }
  };

  const processInline = (text: string): string => {
    // Bold **text**
    text = text.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
    // Links [text](url)
    text = text.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2">$1</a>');
    return text;
  };

  lines.forEach((line, index) => {
    // Headings
    if (line.startsWith('### ')) {
      flushList();
      inList = false;
      elements.push(<h3 key={index}>{line.substring(4)}</h3>);
    } else if (line.startsWith('## ')) {
      flushList();
      inList = false;
      elements.push(<h2 key={index}>{line.substring(3)}</h2>);
    } else if (line.startsWith('# ')) {
      flushList();
      inList = false;
      elements.push(<h1 key={index}>{line.substring(2)}</h1>);
    }
    // List items
    else if (line.startsWith('- ') || line.match(/^\d+\.\s/)) {
      inList = true;
      const content = line.replace(/^[-\d.]+\s/, '');
      listItems.push(content);
    }
    // Regular paragraph
    else if (line.trim()) {
      flushList();
      inList = false;
      elements.push(
        <p key={index} dangerouslySetInnerHTML={{ __html: processInline(line) }} />
      );
    }
    // Empty line
    else {
      if (inList) {
        flushList();
        inList = false;
      }
    }
  });

  // Flush any remaining list items
  flushList();

  return <div className="markdown-content">{elements}</div>;
}

interface ClaimCardMessageProps {
  content: string;
  card?: ClaimCardType;
  contextualResponse?: ContextualResponse;
  timestamp: Date;
}

export function ClaimCardMessage({ content, card, contextualResponse, timestamp }: ClaimCardMessageProps) {
  const [expandedCards, setExpandedCards] = useState<Set<string>>(new Set());

  const timeString = timestamp.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  const toggleCard = (cardId: string) => {
    setExpandedCards(prev => {
      const next = new Set(prev);
      if (next.has(cardId)) {
        next.delete(cardId);
      } else {
        next.add(cardId);
      }
      return next;
    });
  };

  return (
    <div className="claim-card-message-container">
      <div className="claim-card-message">
        {/* Optional text content before card */}
        {content && (
          <div className="message-intro">
            <p>{content}</p>
          </div>
        )}

        {/* Mode 1: Single claim card */}
        {card && <ClaimCard card={card} />}

        {/* Mode 2: Contextual response with source cards */}
        {contextualResponse && (
          <div className="contextual-response">
            {/* Synthesized response text with markdown rendering */}
            <div className="synthesized-response">
              {renderMarkdown(contextualResponse.synthesized_response)}
            </div>

            {/* Source cards (collapsible) */}
            {contextualResponse.source_cards.length > 0 && (
              <div className="source-cards-section">
                <h4 className="source-cards-header">
                  Sources ({contextualResponse.source_cards.length})
                </h4>
                {contextualResponse.source_cards.map((sourceCard) => (
                  <div key={sourceCard.id} className="source-card-wrapper">
                    <button
                      className="source-card-toggle"
                      onClick={() => toggleCard(sourceCard.id)}
                    >
                      <span className="toggle-icon">
                        {expandedCards.has(sourceCard.id) ? '▼' : '▶'}
                      </span>
                      <span className="source-card-title">{sourceCard.claim_text}</span>
                    </button>
                    {expandedCards.has(sourceCard.id) && (
                      <div className="source-card-content">
                        <ClaimCard card={sourceCard} />
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <span className="message-timestamp">{timeString}</span>
      </div>
    </div>
  );
}
