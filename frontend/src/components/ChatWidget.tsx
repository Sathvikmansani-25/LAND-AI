import { useState, useRef, useEffect } from "react";
import { api } from "../api/client";
import type { ChatResponse } from "../types";

interface Message {
  role: "user" | "bot";
  text: string;
}

const SUGGESTIONS = [
  "Show me the top 5 projects at risk",
  "How many high risk projects are there?",
  "Which department is the bottleneck?",
];

export default function ChatWidget() {
  const [open, setOpen] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: "bot", text: "Hi, I'm LandBot AI 🤖. Ask me about project risk, delays, or bottlenecks." },
  ]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  async function send(text: string) {
    if (!text.trim()) return;
    setMessages((m) => [...m, { role: "user", text }]);
    setInput("");
    setLoading(true);
    try {
      const res = await api.post<ChatResponse>("/api/chatbot", { message: text });
      setMessages((m) => [...m, { role: "bot", text: res.response }]);
    } catch {
      setMessages((m) => [...m, { role: "bot", text: "Sorry, I couldn't process that just now." }]);
    } finally {
      setLoading(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-6 right-6 bg-slate-900 text-white rounded-full w-14 h-14 shadow-lg flex items-center justify-center text-2xl hover:bg-slate-700"
        aria-label="Open LandBot AI"
      >
        🤖
      </button>
    );
  }

  return (
    <div className="fixed bottom-6 right-6 w-80 h-[28rem] bg-white rounded-xl shadow-2xl border border-slate-200 flex flex-col overflow-hidden">
      <div className="bg-slate-900 text-white px-4 py-3 flex items-center justify-between">
        <span className="font-medium text-sm">🤖 LandBot AI</span>
        <button onClick={() => setOpen(false)} className="text-slate-300 hover:text-white text-sm">
          ✕
        </button>
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2 text-sm">
        {messages.map((m, i) => (
          <div
            key={i}
            className={`whitespace-pre-wrap px-3 py-2 rounded-lg max-w-[85%] ${
              m.role === "user" ? "bg-slate-900 text-white ml-auto" : "bg-slate-100 text-slate-800"
            }`}
          >
            {m.text}
          </div>
        ))}
        {loading && <div className="text-slate-400 text-xs">LandBot is thinking...</div>}
        <div ref={bottomRef} />
      </div>
      <div className="border-t border-slate-200 p-2">
        <div className="flex flex-wrap gap-1 mb-2">
          {SUGGESTIONS.map((s) => (
            <button
              key={s}
              onClick={() => send(s)}
              className="text-[11px] bg-slate-100 hover:bg-slate-200 text-slate-600 px-2 py-1 rounded-full"
            >
              {s}
            </button>
          ))}
        </div>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            send(input);
          }}
          className="flex gap-2"
        >
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask LandBot..."
            className="flex-1 border border-slate-300 rounded-lg px-2 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-slate-400"
          />
          <button type="submit" className="bg-slate-900 text-white rounded-lg px-3 text-sm hover:bg-slate-700">
            Send
          </button>
        </form>
      </div>
    </div>
  );
}
