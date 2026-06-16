'use client';

import { useState, useEffect, useRef, useCallback, useMemo, memo } from 'react';
import { flushSync } from 'react-dom';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface ChatMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  created_at: string;
  message_type?: string;
  thinking_steps?: string[];
  tool_uses?: string[];
}

// Memoized message component to prevent re-renders
const MessageComponent = memo(({ message }: { message: ChatMessage }) => {
  return (
    <div
      className={`flex ${message.role === 'user' ? 'justify-end' : 'justify-start'}`}
    >
      <div
        className={`max-w-3xl rounded-lg px-4 py-3 ${
          message.role === 'user'
            ? 'bg-blue-600 text-white'
            : 'bg-white border border-gray-200 text-gray-900'
        }`}
      >
        {/* Show thinking/tool use steps for assistant - Claude Code style */}
        {message.role === 'assistant' && (message.thinking_steps || message.tool_uses) && (
          <div className="mb-4 text-sm space-y-2 border-l-2 border-gray-300 pl-3 py-1">
            {message.thinking_steps?.map((step, i) => (
              <div key={i} className="text-gray-600 italic flex items-start gap-2">
                <span className="opacity-50">💭</span>
                <span className="flex-1">{step}</span>
              </div>
            ))}
            {message.tool_uses?.map((tool, i) => (
              <div key={i} className="text-blue-700 font-mono text-xs bg-blue-50 px-2 py-1 rounded border border-blue-200">
                {tool}
              </div>
            ))}
          </div>
        )}
        {message.role === 'assistant' ? (
          <div className="prose prose-sm max-w-none prose-headings:font-semibold prose-a:text-blue-600 prose-pre:bg-gray-100 prose-pre:text-gray-900">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {message.content}
            </ReactMarkdown>
          </div>
        ) : (
          <div className="whitespace-pre-wrap">{message.content}</div>
        )}
        <div
          className={`text-xs mt-2 ${
            message.role === 'user' ? 'text-blue-100' : 'text-gray-500'
          }`}
        >
          {new Date(message.created_at).toLocaleTimeString([], {
            hour: '2-digit',
            minute: '2-digit',
          })}
        </div>
      </div>
    </div>
  );
});
MessageComponent.displayName = 'MessageComponent';

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  // Streaming state - simplified
  const [streamingResponse, setStreamingResponse] = useState<string>('');
  const [thinkingSteps, setThinkingSteps] = useState<string[]>([]);
  const [toolUses, setToolUses] = useState<string[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadHistory = useCallback(async () => {
    try {
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/chat/messages`);
      if (response.ok) {
        const data = await response.json();
        setMessages(data);
      }
    } catch (error) {
      console.error('Error loading chat history:', error);
    } finally {
      setLoadingHistory(false);
    }
  }, []);

  // Load chat history on mount
  useEffect(() => {
    loadHistory();
  }, [loadHistory]);

  // Auto-scroll - when messages change OR when streaming content updates
  useEffect(() => {
    if (messages.length > 0 || streamingResponse) {
      // Use requestIdleCallback for smoother scrolling that doesn't block input
      const scrollToBottom = () => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
      };

      if ('requestIdleCallback' in window) {
        requestIdleCallback(scrollToBottom);
      } else {
        setTimeout(scrollToBottom, 0);
      }
    }
  }, [messages.length, streamingResponse]);

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      const files = Array.from(e.target.files);
      setSelectedFiles(files);
    }
  }, []);

  const removeFile = useCallback((index: number) => {
    setSelectedFiles((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault();
    if ((!input.trim() && selectedFiles.length === 0) || loading) return;

    const userMessage = input.trim();
    const files = selectedFiles;
    setInput('');
    setSelectedFiles([]);
    setLoading(true);

    // Reset streaming states
    setStreamingResponse('');
    setThinkingSteps([]);
    setToolUses([]);

    // Optimistically add user message
    const tempUserMsg: ChatMessage = {
      id: Date.now(),
      role: 'user',
      content: userMessage + (files.length > 0 ? `\n\n📎 Attached: ${files.map(f => f.name).join(', ')}` : ''),
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, tempUserMsg]);

    try {
      // Prepare form data
      const formData = new FormData();
      formData.append('message', userMessage);
      files.forEach((file) => {
        formData.append('files', file);
      });

      // Send to agentic endpoint with streaming
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const response = await fetch(`${apiUrl}/api/chat/messages/agentic`, {
        method: 'POST',
        body: formData,
        // Critical: disable any response buffering
        cache: 'no-store',
      });

      if (!response.ok) {
        throw new Error('Failed to send message');
      }

      // Process streaming response (Server-Sent Events)
      const reader = response.body?.getReader();
      const decoder = new TextDecoder();
      let finalResponse = '';
      let buffer = '';

      // Track collections
      const collectedThinking: string[] = [];
      const collectedTools: string[] = [];

      if (reader) {
        console.log('🔄 Starting to read stream...');

        while (true) {
          const { done, value } = await reader.read();
          if (done) {
            console.log('✅ Stream done, processing remaining buffer...');
            console.log('Buffer length:', buffer.length);
            console.log('Buffer content:', buffer);

            // Process any remaining data in buffer
            if (buffer.trim()) {
              console.log('📦 Processing final buffer (length:', buffer.length, ')');

              // Split on double newlines but also handle incomplete events
              const lines = buffer.split('\n\n').filter(line => line.trim());
              console.log('Found', lines.length, 'lines in buffer');

              for (let i = 0; i < lines.length; i++) {
                const line = lines[i];
                console.log(`Processing line ${i}:`, line.substring(0, 100));

                if (line.startsWith('data: ')) {
                  try {
                    const jsonStr = line.substring(6).trim();
                    const data = JSON.parse(jsonStr);
                    console.log('⚡ FINAL SSE Event:', data.type, 'content length:', data.content?.length);

                    if (data.type === 'thinking') {
                      collectedThinking.push(data.content);
                    } else if (data.type === 'tool_use') {
                      collectedTools.push(data.content);
                    } else if (data.type === 'response_chunk') {
                      finalResponse += data.content;
                    } else if (data.type === 'response' || data.type === 'response_complete') {
                      if (data.content && !finalResponse) {
                        finalResponse = data.content;
                      }
                      console.log('First 200 chars:', finalResponse.substring(0, 200));
                    }
                  } catch (e) {
                    console.error('❌ Final parse error:', e, 'Line:', line);
                  }
                } else if (line.trim() && !line.startsWith('data:')) {
                  console.warn('⚠️ Line does not start with "data:":', line);
                }
              }
            } else {
              console.log('⚠️ Buffer is empty!');
            }

            // Final UI update with all collected data
            setThinkingSteps([...collectedThinking]);
            setToolUses([...collectedTools]);
            setStreamingResponse(finalResponse);
            break;
          }

          // Decode chunk and add to buffer
          const chunk = decoder.decode(value, { stream: true });
          console.log('📦 Received chunk:', chunk.substring(0, 100));
          buffer += chunk;

          // Process complete lines (ending with \n\n)
          let boundary = buffer.indexOf('\n\n');

          while (boundary !== -1) {
            const message = buffer.substring(0, boundary);
            buffer = buffer.substring(boundary + 2);

            // Parse the SSE message
            if (message.startsWith('data: ')) {
              try {
                const jsonStr = message.substring(6);
                const data = JSON.parse(jsonStr);

                console.log('⚡ SSE Event:', data.type, '-', data.content?.substring(0, 50));

                if (data.type === 'thinking') {
                  collectedThinking.push(data.content);
                  console.log('💭 Thinking:', collectedThinking.length, 'steps');
                } else if (data.type === 'tool_use') {
                  collectedTools.push(data.content);
                  console.log('🔧 Tool use:', collectedTools.length, 'tools');
                } else if (data.type === 'response_chunk') {
                  // Stream response in real-time!
                  finalResponse += data.content;
                  console.log('📝 Response chunk, total length:', finalResponse.length);
                  queueMicrotask(() => {
                    setStreamingResponse(finalResponse);
                  });
                } else if (data.type === 'response' || data.type === 'response_complete') {
                  if (data.content && !finalResponse) {
                    finalResponse = data.content;
                  }
                  console.log('✅ Response complete, total length:', finalResponse.length);
                }
              } catch (e) {
                console.error('❌ Parse error:', e);
              }
            }

            boundary = buffer.indexOf('\n\n');
          }
        }
      }

      console.log('📊 Final thinking:', collectedThinking.length);
      console.log('📊 Final tools:', collectedTools.length);
      console.log('📊 Final response length:', finalResponse.length);

      // Add final assistant response
      const assistantMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: finalResponse,
        created_at: new Date().toISOString(),
        thinking_steps: collectedThinking,
        tool_uses: collectedTools.map(t => `🔧 ${t}`),
      };
      setMessages((prev) => [...prev, assistantMsg]);

      // Reset streaming states
      setStreamingResponse('');
      setThinkingSteps([]);
      setToolUses([]);
    } catch (error) {
      console.error('Error sending message:', error);
      // Show error message
      const errorMsg: ChatMessage = {
        id: Date.now() + 1,
        role: 'assistant',
        content: 'Sorry, something went wrong. Please try again.',
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setLoading(false);
    }
  };

  if (loadingHistory) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gray-50">
      {/* Header */}
      <div className="bg-white border-b border-gray-200 px-6 py-4">
        <h1 className="text-2xl font-bold text-gray-900">🤖 CAiS Intelligent Assistant</h1>
        <p className="text-sm text-gray-600 mt-1">
          Ask complex questions, upload images/PDFs, or brain dump what's on your mind
        </p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-6 py-4 space-y-4">
        {messages.length === 0 && (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">🧠</div>
            <h2 className="text-xl font-semibold text-gray-900 mb-2">
              Your Intelligent AI Sidekick
            </h2>
            <p className="text-gray-600 max-w-md mx-auto mb-6">
              I can search your entire journal history, analyze patterns, and answer complex questions.
              I'll show you my thinking process and what tools I use.
            </p>
            <div className="mt-6 space-y-2 text-left max-w-md mx-auto">
              <p className="text-sm text-gray-700 font-medium">Try asking:</p>
              <div className="space-y-1">
                <p className="text-sm text-gray-600">• "What patterns do you see in my conversations with construction people?"</p>
                <p className="text-sm text-gray-600">• "Show me all high-priority tasks and who they're for"</p>
                <p className="text-sm text-gray-600">• "Analyze this invoice" (+ upload image)</p>
              </div>
            </div>
          </div>
        )}

        {messages.map((message) => (
          <MessageComponent key={message.id} message={message} />
        ))}

        {/* Streaming response */}
        {loading && streamingResponse && (
          <div className="flex justify-start">
            <div className="max-w-3xl rounded-lg px-4 py-3 bg-white border border-gray-200 text-gray-900">
              <div className="prose prose-sm max-w-none prose-headings:font-semibold prose-a:text-blue-600 prose-pre:bg-gray-100 prose-pre:text-gray-900">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {streamingResponse}
                </ReactMarkdown>
                <span className="inline-block w-2 h-4 bg-blue-600 animate-pulse ml-1"></span>
              </div>

              {/* Show thinking/tools at bottom in collapsed section */}
              {(thinkingSteps.length > 0 || toolUses.length > 0) && (
                <details className="mt-4 pt-3 border-t border-gray-200">
                  <summary className="text-xs text-gray-500 cursor-pointer hover:text-gray-700">
                    Show details ({thinkingSteps.length} thinking steps, {toolUses.length} tools used)
                  </summary>
                  <div className="mt-2 text-sm space-y-2">
                    {thinkingSteps.map((step, i) => (
                      <div key={i} className="text-gray-600 italic">💭 {step}</div>
                    ))}
                    {toolUses.map((tool, i) => (
                      <div key={i} className="text-blue-700 font-mono text-xs">🔧 {tool}</div>
                    ))}
                  </div>
                </details>
              )}
            </div>
          </div>
        )}

        {/* Loading indicator */}
        {loading && !streamingResponse && (
          <div className="flex justify-start">
            <div className="max-w-3xl rounded-lg px-4 py-3 bg-white border border-gray-200">
              <div className="flex items-center gap-2">
                <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-blue-600"></div>
                <span className="text-gray-600">Thinking...</span>
              </div>
            </div>
          </div>
        )}


        <div ref={messagesEndRef} />
      </div>

      {/* File preview */}
      {selectedFiles.length > 0 && (
        <div className="bg-gray-100 border-t border-gray-200 px-6 py-3">
          <div className="max-w-4xl mx-auto">
            <p className="text-sm text-gray-700 mb-2">Attached files:</p>
            <div className="flex flex-wrap gap-2">
              {selectedFiles.map((file, index) => (
                <div
                  key={index}
                  className="flex items-center gap-2 bg-white px-3 py-2 rounded-lg border border-gray-300"
                >
                  <span className="text-sm text-gray-700">
                    {file.type.startsWith('image/') ? '🖼️' : '📄'} {file.name}
                  </span>
                  <button
                    onClick={() => removeFile(index)}
                    className="text-red-600 hover:text-red-800"
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Input */}
      <div className="bg-white border-t border-gray-200 px-6 py-4">
        <form onSubmit={sendMessage} className="max-w-4xl mx-auto">
          <div className="flex gap-3">
            <input
              type="file"
              ref={fileInputRef}
              onChange={handleFileSelect}
              accept="image/*,.pdf"
              multiple
              className="hidden"
            />
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              className="px-4 py-3 border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors"
              title="Attach files"
            >
              📎
            </button>
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask anything or brain dump what happened..."
              className="flex-1 px-4 py-3 border border-gray-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500"
              disabled={loading}
              autoComplete="off"
            />
            <button
              type="submit"
              disabled={(!input.trim() && selectedFiles.length === 0) || loading}
              className="px-6 py-3 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors font-medium"
            >
              Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
