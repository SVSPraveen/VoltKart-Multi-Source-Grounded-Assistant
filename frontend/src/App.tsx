import React, { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Header } from './components/Header';
import { MessageThread } from './components/MessageThread';
import { Composer } from './components/Composer';
import { EvidenceDrawer } from './components/EvidenceDrawer';
import { IngestionModal } from './components/IngestionModal';
import { ChatMessage, ChatSession, Citation, FileRecord, IngestionSummary } from './types';

export const App: React.FC = () => {
  const [chats, setChats] = useState<ChatSession[]>([]);
  const [activeChatId, setActiveChatId] = useState<string>('');
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [files, setFiles] = useState<FileRecord[]>([]);
  const [isDrawerOpen, setIsDrawerOpen] = useState<boolean>(false);
  const [isMobileSidebarOpen, setIsMobileSidebarOpen] = useState<boolean>(false);
  const [activeCitation, setActiveCitation] = useState<Citation | null>(null);
  const [isSummaryOpen, setIsSummaryOpen] = useState<boolean>(false);
  const [summaryData, setSummaryData] = useState<IngestionSummary | null>(null);
  const [streamingStatus, setStreamingStatus] = useState<string | null>(null);
  const [isSending, setIsSending] = useState<boolean>(false);

  // Initial load: Fetch chats, files, and ingestion summary
  useEffect(() => {
    fetchChats();
    fetchFiles();
    fetchSummary();
  }, []);

  // When activeChatId changes, fetch messages
  useEffect(() => {
    if (activeChatId) {
      fetchMessages(activeChatId);
    }
  }, [activeChatId]);

  const fetchChats = async () => {
    try {
      const res = await fetch('/api/chats');
      if (res.ok) {
        const data: ChatSession[] = await res.json();
        setChats(data);
        if (data.length > 0 && !activeChatId) {
          setActiveChatId(data[0].chat_id);
        } else if (data.length === 0) {
          handleNewChat();
        }
      }
    } catch (err) {
      console.error('Failed to fetch chats:', err);
    }
  };

  const fetchMessages = async (chatId: string) => {
    try {
      const res = await fetch(`/api/chats/${chatId}/messages`);
      if (res.ok) {
        const data = await res.json();
        setMessages(data.messages || []);
      }
    } catch (err) {
      console.error('Failed to fetch messages:', err);
    }
  };

  const fetchFiles = async () => {
    try {
      const res = await fetch('/api/files');
      if (res.ok) {
        const data: FileRecord[] = await res.json();
        setFiles(data);
      }
    } catch (err) {
      console.error('Failed to fetch files:', err);
    }
  };

  const fetchSummary = async () => {
    try {
      const res = await fetch('/api/ingestion-summary');
      if (res.ok) {
        const data: IngestionSummary = await res.json();
        setSummaryData(data);
      }
    } catch (err) {
      console.error('Failed to fetch summary:', err);
    }
  };

  const handleNewChat = async () => {
    // If the active chat already has 0 messages, keep focus on it
    if (messages.length === 0 && activeChatId) {
      return;
    }
    try {
      const res = await fetch('/api/chats', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ title: 'New Conversation' }),
      });
      if (res.ok) {
        const newChat: ChatSession = await res.json();
        setChats((prev) => [newChat, ...prev.filter((c) => c.chat_id !== newChat.chat_id)]);
        setActiveChatId(newChat.chat_id);
        setMessages([]);
        setActiveCitation(null);
        setIsDrawerOpen(false);
      }
    } catch (err) {
      console.error('Failed to create new chat:', err);
    }
  };

  const handleDeleteChat = async (chatId: string) => {
    try {
      const res = await fetch(`/api/chats/${chatId}`, { method: 'DELETE' });
      if (res.ok) {
        const remaining = chats.filter((c) => c.chat_id !== chatId);
        setChats(remaining);
        if (activeChatId === chatId && remaining.length > 0) {
          setActiveChatId(remaining[0].chat_id);
          setActiveCitation(null);
          setIsDrawerOpen(false);
        } else if (remaining.length === 0) {
          handleNewChat();
        }
      }
    } catch (err) {
      console.error('Failed to delete chat:', err);
    }
  };

  const handleSendMessage = async (content: string, webEnabled: boolean) => {
    if (!activeChatId) return;

    // Optimistically update chat title in sidebar if it's currently generic
    const firstLine = content.trim().split('\n')[0].trim();
    const cleanTitle = firstLine.slice(0, 40) + (firstLine.length > 40 ? '...' : '');
    setChats((prev) =>
      prev.map((c) =>
        c.chat_id === activeChatId && (c.title === 'New Conversation' || c.title === 'New Chat' || !c.title || c.title === c.chat_id)
          ? { ...c, title: cleanTitle }
          : c
      )
    );

    // Optimistically append user message
    const tempUserMsg: ChatMessage = {
      message_id: `temp_user_${Date.now()}`,
      chat_id: activeChatId,
      role: 'user',
      content,
      web_enabled: webEnabled,
      created_at: new Date().toISOString().substring(11, 19) + ' UTC',
    };
    setMessages((prev) => [...prev, tempUserMsg]);
    setIsSending(true);
    setStreamingStatus('Initializing pipeline...');

    try {
      const response = await fetch(`/api/chats/${activeChatId}/messages`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, web_enabled: webEnabled }),
      });

      if (!response.ok || !response.body) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n\n');
        buffer = lines.pop() || '';

        for (const block of lines) {
          const rawLines = block.split('\n');
          let eventType = '';
          let dataStr = '';

          for (const l of rawLines) {
            if (l.startsWith('event:')) {
              eventType = l.replace('event:', '').trim();
            } else if (l.startsWith('data:')) {
              dataStr = l.replace('data:', '').trim();
            }
          }

          if (eventType === 'status' && dataStr) {
            try {
              const statusData = JSON.parse(dataStr);
              setStreamingStatus(statusData.status);
            } catch {}
          } else if (eventType === 'answer' && dataStr) {
            try {
              const answerData = JSON.parse(dataStr);
              const asstMsg: ChatMessage = {
                message_id: `asst_${Date.now()}`,
                chat_id: activeChatId,
                role: 'assistant',
                content: answerData.content,
                interpreted_as: answerData.interpreted_as,
                citations: answerData.citations || [],
                charts: answerData.charts || [],
                created_at: new Date().toISOString().substring(11, 19) + ' UTC',
              };
              setMessages((prev) => [...prev, asstMsg]);
              if (answerData.citations && answerData.citations.length > 0) {
                setActiveCitation(answerData.citations[0]);
              }
            } catch (err) {
              console.error('Failed to parse answer event:', err);
            }
          }
        }
      }
    } catch (err) {
      console.error('Streaming error:', err);
      const errorMsg: ChatMessage = {
        message_id: `err_${Date.now()}`,
        chat_id: activeChatId,
        role: 'assistant',
        content: `Error generating response: ${err}`,
        created_at: 'Error',
      };
      setMessages((prev) => [...prev, errorMsg]);
    } finally {
      setIsSending(false);
      setStreamingStatus(null);
      fetchChats();
    }
  };

  const handleUploadFiles = async (selectedFiles: FileList) => {
    const formData = new FormData();
    for (let i = 0; i < selectedFiles.length; i++) {
      formData.append('files', selectedFiles[i]);
    }

    try {
      setStreamingStatus('Uploading and parsing files...');
      const res = await fetch('/api/upload', {
        method: 'POST',
        body: formData,
      });
      if (res.ok) {
        const summary: IngestionSummary = await res.json();
        setSummaryData(summary);
        setIsSummaryOpen(true);
        fetchFiles();
      }
    } catch (err) {
      console.error('Upload failed:', err);
    } finally {
      setStreamingStatus(null);
    }
  };

  const handleExportPdf = () => {
    if (!activeChatId) return;
    window.open(`/api/chats/${activeChatId}/export.pdf`, '_blank');
  };

  const handleSelectCitation = (cit: Citation) => {
    setActiveCitation(cit);
    setIsDrawerOpen(true);
  };

  const currentChat = chats.find((c) => c.chat_id === activeChatId);
  const allCitationsInChat = messages.flatMap((m) => m.citations || []);

  return (
    <div style={{ display: 'flex', width: '100vw', height: '100vh', overflow: 'hidden' }}>
      {/* Left Rail: Chats & Versioned Files Library */}
      <Sidebar
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={(id) => {
          if (id !== activeChatId) {
            setActiveChatId(id);
            setActiveCitation(null);
            setIsDrawerOpen(false);
          }
          setIsMobileSidebarOpen(false);
        }}
        onNewChat={handleNewChat}
        onDeleteChat={handleDeleteChat}
        files={files}
        onOpenSummary={() => setIsSummaryOpen(true)}
        isOpen={isMobileSidebarOpen}
        onCloseMobile={() => setIsMobileSidebarOpen(false)}
      />

      {/* Main Center Area */}
      <main style={{
        flex: 1,
        display: 'flex',
        flexDirection: 'column',
        height: '100vh',
        overflow: 'hidden',
        backgroundColor: 'var(--bg-paper)',
      }}>
        <Header
          chatTitle={currentChat?.title || 'Conversation'}
          chatId={activeChatId}
          onNewChat={handleNewChat}
          onExportPdf={handleExportPdf}
          onToggleDrawer={() => setIsDrawerOpen((prev) => !prev)}
          isDrawerOpen={isDrawerOpen}
          onOpenSummary={() => setIsSummaryOpen(true)}
          onToggleMobileSidebar={() => setIsMobileSidebarOpen((prev) => !prev)}
        />


        <MessageThread
          messages={messages}
          streamingStatus={streamingStatus}
          onSelectCitation={handleSelectCitation}
        />

        <Composer
          onSendMessage={handleSendMessage}
          onUploadFiles={handleUploadFiles}
          isSending={isSending}
        />
      </main>

      {/* Right Rail: Evidence Drawer */}
      <EvidenceDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        activeCitation={activeCitation}
        allCitations={allCitationsInChat}
      />

      {/* Ingestion Schema Modal */}
      <IngestionModal
        isOpen={isSummaryOpen}
        onClose={() => setIsSummaryOpen(false)}
        summary={summaryData}
      />
    </div>
  );
};
