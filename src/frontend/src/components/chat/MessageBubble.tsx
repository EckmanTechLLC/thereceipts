/**
 * User message bubble component.
 *
 * Displays user messages as right-aligned chat bubbles.
 */

import './MessageBubble.css';

interface MessageBubbleProps {
  content: string;
  timestamp: Date;
}

export function MessageBubble({ content, timestamp }: MessageBubbleProps) {
  const timeString = timestamp.toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  return (
    <div className="message-bubble-container">
      <div className="message-bubble">
        <p className="message-content">{content}</p>
        <span className="message-timestamp">{timeString}</span>
      </div>
    </div>
  );
}
