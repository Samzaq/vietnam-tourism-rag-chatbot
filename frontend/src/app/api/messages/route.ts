import { promptMessageSchema } from "@/features/chat/schemas/prompt-message-schema";
import { prisma } from "@/lib/prisma";
import { auth } from "@clerk/nextjs/server";
import { notFound, redirect } from "next/navigation";
import { NextRequest } from "next/server";

export const runtime = "nodejs";

export async function POST(req: NextRequest) {
  const url = new URL(req.url);
  const chatId = url.searchParams.get("chatId"); // frontend nên truyền ?chatId=xxx
  const { message, language } = await req.json();

  try {
    const { userId } = await auth();
    if (!userId) redirect("/login");

    const validatedMessage = promptMessageSchema.parse(message);

    let chat;

    // ✅ Nếu có chatId thì tìm trong DB
    if (chatId) {
      chat = await prisma.chat.findFirst({
        where: { id: chatId, userId },
        include: { messages: true },
      });

      if (!chat) {
        console.warn("⚠️ Chat not found for user, creating new chat...");
        chat = await prisma.chat.create({
          data: { userId, title: validatedMessage.content },
          include: { messages: true },
        });
      }
    } else {
      // ✅ Nếu không có chatId, tạo mới (lần đầu)
      chat = await prisma.chat.create({
        data: { userId, title: validatedMessage.content },
        include: { messages: true },
      });
    }

    // ✅ Lưu tin nhắn người dùng
    const userMessage = await prisma.message.create({
      data: { chatId: chat.id, role: "user", ...validatedMessage },
    });

    const messages = chat.messages.concat(userMessage);

    // ✅ Gọi FastAPI
    const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    const fastapiRes = await fetch(`${API_URL}/process`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ messages, id: chat.id, language }),
    });

    if (!fastapiRes.ok || !fastapiRes.body)
      throw new Error("FastAPI không phản hồi hoặc không có stream body");

    const decoder = new TextDecoder();
    const encoder = new TextEncoder();

    let botContent = "";

    const stream = new ReadableStream({
      async start(controller) {
        const reader = fastapiRes.body!.getReader();
        let partial = "";

        while (true) {
          const { done, value } = await reader.read();
          if (done) break;

          partial += decoder.decode(value, { stream: true });
          const lines = partial.split("\n\n");
          partial = lines.pop() || "";

          for (const line of lines) {
            if (!line.startsWith("data:")) continue;

            const dataStr = line.slice(5).trim();

            if (dataStr === "[DONE]") {
              controller.close();
              break;
            }

            try {
              const json = JSON.parse(dataStr);
              if (json?.content) {
                botContent += json.content;
                controller.enqueue(encoder.encode(json.content));
              }
            } catch (err) {
              console.error("Parse JSON error:", err);
            }
          }
        }

        // ✅ Lưu tin nhắn bot sau khi stream xong
        await prisma.message.create({
          data: {
            chatId: chat.id,
            role: "assistant",
            content: botContent,
          },
        });
      },
    });

    return new Response(stream, {
      headers: {
        "Content-Type": "text/plain; charset=utf-8",
        "Cache-Control": "no-cache",
        "X-Chat-Id": chat.id,
      },
    });
  } catch (error) {
    console.error("❌ Chat route error:", error);
    return new Response(JSON.stringify({ error: String(error) }), {
      status: 500,
    });
  }
}
