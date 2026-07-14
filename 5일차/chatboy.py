import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

RAG_SAMPLES = os.path.join(os.getcwd(), 'samples', 'rag_samples')
print('RAG_SAMPLES:', RAG_SAMPLES)
for p in sorted(Path(RAG_SAMPLES).glob('*.pdf')):
    print(' -', p.name)

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_chroma import Chroma
import os

text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=100)

# 학칙.pdf
loader = PyPDFLoader(os.path.join(RAG_SAMPLES, '학칙.pdf'))
all_splits = text_splitter.split_documents(loader.load())

# news.pdf
loader_news = PyPDFLoader(os.path.join(RAG_SAMPLES, 'news.pdf'))
news_splits = text_splitter.split_documents(loader_news.load())
all_splits.extend(news_splits)

embedding = OpenAIEmbeddings(
    model='text-embedding-3-large', api_key=OPENAI_API_KEY
)

persist_directory = 'chroma_store'	

# 저장된 크로마 DB가 없다면 새로 만들기
if not os.path.exists(persist_directory):
    print("Creating new Chroma store")
    vectorstore = Chroma.from_documents(
        documents=all_splits,
        embedding=embedding,
        persist_directory=persist_directory
    )

else:
    print("Loading existing Chroma store")
    vectorstore = Chroma(		
        persist_directory=persist_directory, 
        embedding_function=embedding
    )
retriever = vectorstore.as_retriever(search_kwargs={'k': 3})

from langchain_core.tools import create_retriever_tool

search_pdf_tool = create_retriever_tool(
    retriever,
    name='search_pdf_documents',
    description='pdf samples 안의 문서함에서 질문과 관련된 내용을 검색합니다.',
)

from datetime import datetime
import pytz
import yfinance as yf
from langchain_core.tools import tool

@tool
def get_current_time(timezone: str, location: str) -> str:
    """현재 시각. timezone 예: Asia/Seoul, location 예: 서울"""
    tz = pytz.timezone(timezone)
    now = datetime.now(tz).strftime('%Y-%m-%d %H:%M:%S')
    return f'{timezone} ({location}) 현재시각 {now}'

@tool
def get_yf_stock_history(ticker: str, period: str) -> str:
    """주식 가격 조회. ticker 예: TSLA, period 예: 1mo"""
    history = yf.Ticker(ticker).history(period=period)
    return history.tail(3).to_string() if not history.empty else '데이터 없음'



from langchain_community.tools import DuckDuckGoSearchResults

web_search = DuckDuckGoSearchResults(num_results=3)
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

llm = ChatOpenAI(model='gpt-4o-mini', temperature=0.1)

agent_tools = [get_current_time, get_yf_stock_history, search_pdf_tool, web_search]
print([t.name for t in agent_tools])

prompt = ChatPromptTemplate.from_messages([
    ('system', '''너는 사용자를 돕는 AI입니다. 질문에 맞는 도구를 골라 사용하세요.

- samples/rag_samples PDF (학칙, news 등) → search_pdf_documents
- 최신 뉴스·시사·웹 정보 → duckduckgo_results_json
- 주가 → get_yf_stock_history
- 현재 시각 → get_current_time

도구 결과에 없으면 추측하지 마세요. 한국어로 답하세요.'''),
    MessagesPlaceholder('chat_history', optional=True),
    ('human', '{input}'),
    MessagesPlaceholder('agent_scratchpad'),
])

agent = create_tool_calling_agent(llm, agent_tools, prompt)
executor = AgentExecutor(agent=agent, tools=agent_tools, verbose=True, max_iterations=8)
from langchain_core.messages import HumanMessage, AIMessage

class ChatSession:
    def __init__(self, executor):
        self.executor = executor
        self.history = []

    def ask(self, question: str) -> str:
        result = self.executor.invoke({'input': question, 'chat_history': self.history})
        answer = result['output']
        self.history.extend([HumanMessage(content=question), AIMessage(content=answer)])
        return answer

session = ChatSession(executor)
print('종료: exit')
while True:
    user_input = input('사용자: ').strip()
    if user_input.lower() in ('exit', 'quit', '종료'):
        break
    if not user_input:
        continue
    print('AI:', session.ask(user_input))