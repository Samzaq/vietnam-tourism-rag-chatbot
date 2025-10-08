"use client";

import { Chat, Message, Prisma } from "@prisma/client";
import { MessageClient } from "../types/message";

// Extend ChatClient to include messages property
export interface ChatClient {
  id: string;
  title: string;
  messages: MessageClient[];
}

import React, {
  createContext,
  useContext,
  useState,
  ReactNode,
  FormEvent,
  useEffect,
} from "react";

type WithMessagesChat = Prisma.ChatGetPayload<{ include: { messages: true } }>;

interface ChatContextType {
  messages: MessageClient[];
  setMessages: React.Dispatch<React.SetStateAction<MessageClient[]>>;
  input: string;
  setInput: React.Dispatch<React.SetStateAction<string>>;
  history: ChatClient[];
  setHistory: React.Dispatch<React.SetStateAction<ChatClient[]>>;
  selectedChat: string | null;
  setSelectedChat: React.Dispatch<React.SetStateAction<string | null>>;
  sidebarOpen: true | false;
  setSidebarOpen: React.Dispatch<React.SetStateAction<true | false>>;
  isTyping: true | false;
  setIsTyping: React.Dispatch<React.SetStateAction<true | false>>;
  theme: "light" | "dark";
  language: "Tiếng Việt" | "English";
  setLanguage: React.Dispatch<React.SetStateAction<"Tiếng Việt" | "English">>;
  handleLanguageChange: (event: React.ChangeEvent<HTMLSelectElement>) => void;
  toggleTheme: () => void;
  toggleSidebar: () => void;
  startNewChat: () => void;
  handleSubmit: (event: FormEvent) => Promise<void>;
  handleSuggestionClick: (question: string) => void;
}

const ChatContext = createContext<ChatContextType | undefined>(undefined);

export const ChatProvider = ({
  chat,
  children,
}: {
  chat?: WithMessagesChat;
  children: ReactNode;
}) => {
  const [messages, setMessages] = useState<MessageClient[]>([]);
  const [input, setInput] = useState("");
  const [history, setHistory] = useState<ChatClient[]>([]);
  const [selectedChat, setSelectedChat] = useState<string | null>(null);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [isTyping, setIsTyping] = useState(false);
  const [language, setLanguage] = useState<"Tiếng Việt" | "English">("Tiếng Việt");
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    if (typeof window !== "undefined") {
      const savedTheme = localStorage.getItem("theme");
      return savedTheme ? (savedTheme as "light" | "dark") : "light";
    }
    return "light";
  });

  useEffect(() => {
    if (chat) {
      setMessages(chat.messages);
      setSelectedChat(chat.id);
    }
  }, [chat]);
  // Hiệu ứng typing từng chữ

  const toggleTheme = () => {
    const newTheme = theme === "light" ? "dark" : "light";
    setTheme(newTheme);
    // Lưu theme vào localStorage
    if (typeof window !== "undefined") {
      localStorage.setItem("theme", newTheme);
    }
  };

  const toggleSidebar = () => {
    setSidebarOpen((prev) => !prev); // Toggle trạng thái mở/đóng của sidebar
  };

  const startNewChat = () => {
    setSelectedChat(null);
    setMessages([]);
  };

  const typeTextEffect = async (
    text: string,
    update: (partial: string) => void,
    typingDelay = 10 // tốc độ gõ (ms mỗi ký tự)
  ) => {
    for (let i = 0; i < text.length; i++) {
      update(text.slice(0, i + 1));
      await new Promise((resolve) => setTimeout(resolve, typingDelay));
    }
  };


  const handleSubmit = async (event: FormEvent) => {
    event?.preventDefault();
    if (!input.trim()) return;

    const newMessage: MessageClient = { role: "user", content: input };
    setMessages((prev) => [...prev, newMessage]);
    setInput("");
    setIsTyping(true);

    try {
      const res = await fetch(`/api/messages?chatId=${selectedChat || ""}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: newMessage,
          language,
        }),
      });

      const chatHeaderId = res.headers.get("X-Chat-Id");
      if (chatHeaderId && !selectedChat) {
        setSelectedChat(chatHeaderId);
      }


      if (!res.ok || !res.body) throw new Error("Streaming failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let botFullText = "";

      // Thêm message assistant rỗng
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
      let firstChunk = true;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        botFullText += chunk;

        if (firstChunk) {
          setIsTyping(false);
          firstChunk = false;
        }


        // typing từng ký tự
        await typeTextEffect(chunk, (partialText) => {
          if (isTyping) {
            setIsTyping(false); // ẩn dấu "..."
          }
          setMessages((prev) => {
            const updated = [...prev];
            const lastIndex = updated.findLastIndex((m) => m.role === "assistant");
            if (lastIndex !== -1) {
              updated[lastIndex] = {
                role: "assistant",
                content: botFullText.slice(
                  0,
                  botFullText.length - chunk.length + partialText.length
                ),
              };
            }
            return updated;
          });
        });
      }

      setIsTyping(false);
    } catch (err) {
      console.error("Streaming error:", err);
      setIsTyping(false);
    }
  };

  const handleSuggestionClick = async (question: string) => {
    if (!question.trim()) return;

    const newMessage: MessageClient = { role: "user", content: question };
    setMessages((prev) => [...prev, newMessage]);
    setIsTyping(true);

    try {
      const res = await fetch(`/api/messages?chatId=${selectedChat || ""}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: newMessage,
          language,
        }),
      });

      const chatHeaderId = res.headers.get("X-Chat-Id");
      if (chatHeaderId && !selectedChat) {
        setSelectedChat(chatHeaderId);
      }


      if (!res.ok || !res.body) throw new Error("Streaming failed");

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let botFullText = "";

      // Thêm assistant message rỗng
      setMessages((prev) => [...prev, { role: "assistant", content: "" }]);
      let firstChunk = true;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        botFullText += chunk;

        if (firstChunk) {
          setIsTyping(false);
          firstChunk = false;
        }



        await typeTextEffect(chunk, (partialText) => {
          if (isTyping) {
            setIsTyping(false); // ẩn dấu "..."
          }
          setMessages((prev) => {
            const updated = [...prev];
            const lastIndex = updated.findLastIndex((m) => m.role === "assistant");
            if (lastIndex !== -1) {
              updated[lastIndex] = {
                role: "assistant",
                content: botFullText.slice(
                  0,
                  botFullText.length - chunk.length + partialText.length
                ),
              };
            }
            return updated;
          });
        });
      }

      setIsTyping(false);
    } catch (err) {
      console.error("Streaming error:", err);
      setIsTyping(false);
    }
  };




  const handleLanguageChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const selectedLanguage = event.target.value as "Tiếng Việt" | "English";
    setLanguage(selectedLanguage);
  };

  return (
    <ChatContext.Provider
      value={{
        messages,
        setMessages,
        input,
        setInput,
        history,
        setHistory,
        selectedChat,
        setSelectedChat,
        theme,
        toggleTheme,
        startNewChat,
        handleSuggestionClick,
        handleSubmit,
        toggleSidebar,
        sidebarOpen,
        setSidebarOpen,
        isTyping,
        setIsTyping,
        language,
        setLanguage,
        handleLanguageChange,
      }}
    >
      {children}
    </ChatContext.Provider>
  );
};

export const useChat = () => {
  const context = useContext(ChatContext);
  if (!context) {
    throw new Error("useChat must be used within a ChatProvider");
  }
  return context;
};
