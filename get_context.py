import os
import asyncio
import tiktoken
import re
from openai import AsyncOpenAI
from dotenv import load_dotenv
from tqdm.asyncio import tqdm_asyncio

class CodebaseProcessor:
    def __init__(self, api_key, model_name="deepseek-chat"):
        self.api_key = api_key
        self.model_name = model_name
        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )
        self.tokenizer = tiktoken.get_encoding("cl100k_base")
        self.max_total_tokens = 64000
        self.chunk_size_tokens = 6000
        self.excluded_dirs = {'__pycache__', '.venv', '.pytest_cache', '.vscode', '.git'}
        self.excluded_file_exts = {
            '.log', '.md', '.txt', '.csv', '.json', '.yaml', '.yml', '.lock', '.env',
            '.png', '.jpg', '.jpeg', '.gif', '.ico', '.svg', '.pdf', '.bin'  # Added binary file extensions
        }
        self.max_file_size = 100000
        self.rate_limit_semaphore = asyncio.Semaphore(10)
        self.retry_attempts = 3
        self.code_block_pattern = re.compile(r'```(?:[a-zA-Z]+)?\n(.*?)\n```', re.DOTALL)

    def chunk_codebase(self, root_dir):
        chunks = []
        for root, dirs, files in os.walk(root_dir):
            dirs[:] = [d for d in dirs if d not in self.excluded_dirs]
            for file in files:
                file_path = os.path.join(root, file)
                if self._should_process(file_path):
                    try:
                        with open(file_path, "rb") as f:
                            content = f.read().decode('utf-8')
                        file_chunks = self._chunk_content(content, file_path)
                        chunks.extend(file_chunks)
                    except UnicodeDecodeError:
                        print(f"Skipping binary file: {file_path}")
                    except Exception as e:
                        print(f"Error reading {file_path}: {str(e)}")
        return chunks

    def _should_process(self, file_path):
        if "env" in file_path.lower() or "secret" in file_path.lower():
            return False
        if os.path.getsize(file_path) > self.max_file_size:
            return False
        return (
            os.path.splitext(file_path)[1].lower() not in self.excluded_file_exts and
            self._is_likely_text_file(file_path)
        )

    def _is_likely_text_file(self, file_path):
        try:
            with open(file_path, 'rb') as f:
                chunk = f.read(1024)
                return b'\0' not in chunk and chunk.decode('utf-8', errors='ignore').isprintable()
        except Exception:
            return False

    def _chunk_content(self, content, file_path):
        tokens = self.tokenizer.encode(content)
        return [{
            "file_path": file_path,
            "content": self.tokenizer.decode(tokens[i:i+self.chunk_size_tokens]),
            "token_count": len(tokens[i:i+self.chunk_size_tokens])
        } for i in range(0, len(tokens), self.chunk_size_tokens)]

    async def process_chunks(self, question, chunks):
        tasks = [self._get_relevant_context(question, chunk) for chunk in chunks]
        responses = await tqdm_asyncio.gather(*tasks, desc="Processing")
        return self._process_responses(responses)

    async def _get_relevant_context(self, question, chunk):
        async with self.rate_limit_semaphore:
            for attempt in range(self.retry_attempts):
                try:
                    response = await self.client.chat.completions.create(
                        model=self.model_name,
                        messages=[{
                            "role": "user",
                            "content": f"Return ONLY raw code from this chunk relevant to: {question}\n\n{chunk['content']}"
                        }],
                        temperature=0.2,
                        max_tokens=2000
                    )
                    return response.choices[0].message.content
                except Exception:
                    await asyncio.sleep(2 ** attempt)
        return None

    def _process_responses(self, responses):
        code_blocks = []
        seen_blocks = set()
        
        for response in filter(None, responses):
            blocks = self.code_block_pattern.findall(response)
            for block in blocks:
                clean_block = block.strip()
                if clean_block and clean_block not in seen_blocks:
                    seen_blocks.add(clean_block)
                    code_blocks.append(clean_block)
        
        combined = "\n\n".join(code_blocks)
        tokens = self.tokenizer.encode(combined)
        
        if len(tokens) > self.max_total_tokens:
            return self.tokenizer.decode(tokens[:self.max_total_tokens])
        return combined

async def main(question: str):
    load_dotenv()
    processor = CodebaseProcessor(os.getenv("DEEPSEEK_API_KEY"))
    chunks = processor.chunk_codebase(os.getcwd())
    
    if not chunks:
        print("No code chunks found")
        return ""

    context = await processor.process_chunks(question, chunks)
    with open("context.txt", "w", encoding="utf-8") as f:
        f.write(context)
    return context

if __name__ == "__main__":
    import sys
    question = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Question: ")
    asyncio.run(main(question))