from ollama import chat
import os
from retriever import Retriever
from smooth_context import smooth_contexts
from data_loader import load_meta_corpus
from typing import List, Dict
from openai import OpenAI, AsyncOpenAI
from dotenv import load_dotenv
import chromadb
import pprint
import time

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=api_key)

CHROMA_DB_DIR = "data/chroma_db"
chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
collection = chroma_client.get_collection(name="vietnam_tourism")

prompt_template = (
    """###Yêu cầu: Bạn là một trợ lý du lịch thông minh, chuyên cung cấp câu trả lời dựa trên thông tin được truy xuất từ hệ thống về du lịch Việt Nam. Khi nhận được dữ liệu truy xuất từ RAG, hãy:  

    1. Phân tích dữ liệu để trả lời đúng trọng tâm câu hỏi của người dùng. Chỉ trả lời dựa trên dữ liệu được cung cấp, không suy đoán hoặc tạo ra thông tin mới.
    2. Tóm tắt thông tin một cách rõ ràng, ngắn gọn nhưng vẫn đầy đủ ý nghĩa.  
    3. Trả lời với giọng điệu thân thiện và dễ tiếp cận.  
    4. Nếu dữ liệu truy xuất không có thông tin liên quan đến câu hỏi hoặc không có dữ liệu nào được truy xuất, hãy trả lời: "Xin lỗi, tôi không có thông tin phù hợp để trả lời câu hỏi này."  
    5. Nếu câu hỏi không liên quan đến chủ đề du lịch Việt Nam (out domain) hãy giới thiệu lịch sự về lĩnh vực của mình.
    6. Trả lời câu hỏi bằng ngôn ngữ: {language}

    ###Dựa vào một số ngữ cảnh truy xuất được dưới đây nếu bạn thấy nó có liên quan đến câu hỏi thì trả lời câu hỏi ở cuối. {input}
    ###Câu hỏi từ người dùng: {question}
    ###Nếu thấy ngữ cảnh có liên quan đến câu hỏi hãy trả lời chi tiết và đầy đủ dựa trên ngữ cảnh."""
)

def get_prompt(question, contexts, language):
    # context = "\n\n".join([f"Context [{i+1}]: {x['passage']}" for i, x in enumerate(contexts)])
    context = "\n\n".join([f"Context [{i+1}]: {x}" for i, x in enumerate(contexts)])

    input = f"\n\n{context}\n\n"
    prompt = prompt_template.format(
        input=input,
        question=question, 
        language=language
    )
    return prompt


def classify_small_talk(input_sentence, language):
    prompt = f"""
    ###Yêu cầu: Bạn là một trợ lý hữu ích được thiết kế để phân loại các câu hỏi của người dùng trong ngữ cảnh của một chatbot du lịch Việt Nam. Nhiệm vụ của bạn là xác định liệu câu hỏi của người dùng có phải là "small talk" hay không"
    ###"Small talk" đề cập đến những chủ đề trò chuyện thông thường, không liên quan trực tiếp đến du lịch Việt Nam, chẳng hạn như chào hỏi, câu hỏi cá nhân, câu chuyện cười.
    Nếu câu hỏi không phải là small talk và liên quan đến du lịch, ẩm thực, điểm đến, hoạt động, bạn PHẢI có từ "no" trong câu trả lời và trả về "no."
    Nếu câu hỏi là small talk: Không trả lời câu hỏi mà hãy giới thiệu về chatbot tư vấn du lịch Việt Nam một cách ngắn gọn với giọng điệu cuốn hút bằng ngôn ngữ: {language}.

    ###Ví dụ:
    User query: "Chào bạn, hôm nay thế nào?"
    Response: "Cảm ơn bạn đã quan tâm! Mình là chatbot tư vấn du lịch Việt Nam, sẵn sàng hỗ trợ bạn khám phá các điểm đến tuyệt đẹp, món ăn hấp dẫn và nhiều hoạt động thú vị. Hãy hỏi mình bất cứ điều gì liên quan đến du lịch nhé! 😊"
    User query: "Ở đó có món gì ngon?"
    Response: "no"
    User query: "Bạn có thích đi du lịch không?"
    Response: "Mình là chatbot tư vấn du lịch Việt Nam, luôn sẵn sàng hỗ trợ bạn khám phá các điểm đến tuyệt vời, ẩm thực hấp dẫn và các hoạt động thú vị. Hãy hỏi tôi bất kỳ điều gì liên quan đến du lịch nhé! 😊"
    User query: "Hà Nội có món ăn nào ngon nhất?"
    Response: "no"
    User query: "Các địa điểm du lịch nổi tiếng ở Huế là gì?"
    Response: "no"
    User query: "Cảm ơn bạn"
    Response: "Cảm ơn bạn đã ghé thăm! Mình là chatbot tư vấn du lịch Việt Nam, luôn sẵn sàng giúp bạn khám phá các điểm đến tuyệt vời, ẩm thực phong phú và nhiều hoạt động thú vị. Hãy hỏi mình bất cứ điều gì liên quan đến du lịch nhé!"
    ###Dựa trên câu hỏi từ người dùng, hãy thực hiện đúng yêu cầu. Câu hỏi từ người dùng: {input_sentence}"""

    completion = client.chat.completions.create(
      model="gpt-4o-mini",
      messages=[
        {"role": "user", "content": prompt}
      ]
    )
    answer = completion.choices[0].message.content
    return answer.strip().lower()

# ---- Chroma-based Retrieval ----
def chroma_retrieve(query, topk=5):
    results = collection.query(query_texts=[query], n_results=topk)
    return results["documents"][0] if results and "documents" in results else []

def create_new_prompt(prompt, chat_history, user_query, **kwargs):
  new_prompt = f"{prompt} lịch sử cuộc trò chuyện: {chat_history} câu hỏi của người dùng: {user_query}"
  for key, value in kwargs.items():
    new_prompt += f" {key}: {value}"

  return new_prompt

def chatbot(conversation_history: List[Dict[str, str]], language: str):
    """
    Async generator that yields chunks of text as they are generated.
    """
    user_query = conversation_history[-1]['content']

    meta_corpus = load_meta_corpus(r"data/corpus_chunks.jsonl")

    # Detect small talk
    result = classify_small_talk(user_query, language)
    print("result classify small talk:", result)

    # If it's small talk
    if "no" not in result:
        yield result
        return

    # If not small talk
    prompt_refiner = """Dựa trên lịch sử cuộc trò chuyện và câu hỏi mới nhất của người dùng, có thể tham chiếu đến ngữ cảnh trong lịch sử trò chuyện, 
#             hãy tạo thành một câu hỏi độc lập có thể hiểu được mà không cần lịch sử cuộc trò chuyện và không bị mất đi ngữ cảnh.
#             KHÔNG trả lời câu hỏi, chỉ cần điều chỉnh lại nếu cần, nếu không thì giữ nguyên.
#             Quan trọng và phải giữ được ngữ cảnh của cuộc nói chuyện.
#             Không bị mất đi ngữ cảnh.
#             Nếu câu hỏi bằng tiếng Anh, sau khi tinh chỉnh, hãy dịch câu hỏi đó sang tiếng Việt."""

    new_prompt = create_new_prompt(
        prompt=prompt_refiner,
        chat_history=conversation_history,
        user_query=user_query,
    )

    # Step 1: Generate refined question
    refine = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": new_prompt}],
    )

    answer = refine.choices[0].message.content.strip()
    print("Câu hỏi mới:", answer)
    question = answer

    # Step 2: Retrieve context
    top_passages = chroma_retrieve(question, topk=10)
    print(f"Retrieved {len(top_passages)} passages from Chroma.")
    pprint.pprint(top_passages)

    prompt = get_prompt(question, top_passages, language)

    # Step 3: Stream from OpenAI
    stream = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )

    for chunk in stream:
        if len(chunk.choices) > 0:
            content = getattr(chunk.choices[0].delta, "content", None)
            if content:
                yield content
