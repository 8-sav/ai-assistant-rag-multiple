# app/services/rag_engine.py
import os
import mimetypes
from pathlib import Path
from typing import List, Dict, Tuple
from sentence_transformers import SentenceTransformer
from PyPDF2 import PdfReader
from docx import Document as DocxDocument
from app.services.vector_db import VectorDB

class RAGEngine:
    def __init__(self, vector_db, embedding_model_name, chunk_size, chunk_overlap):
        # Убедимся, что модель загружена локально
        self.embedding_model = SentenceTransformer(embedding_model_name, cache_folder=os.path.expanduser("~/.cache/sentence_transformers"))
        self.vector_db = vector_db
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def _read_text_from_file(self, file_path: str) -> str:
        mime_type, _ = mimetypes.guess_type(file_path)
        text = ""

        if mime_type == 'application/pdf':
            reader = PdfReader(file_path)
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted
        elif mime_type == 'application/vnd.openxmlformats-officedocument.wordprocessingml.document':
            doc = DocxDocument(file_path)
            text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        elif mime_type == 'text/plain' or file_path.endswith('.txt'):
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                text = f.read()
        else:
            raise ValueError(f"Unsupported file type: {mime_type}")

        return text.strip()

    def process_document(self, text: str) -> Tuple[List[str], List[Dict]]:
        chunks = []
        metadata = []

        start = 0
        chunk_id = 0
        while start < len(text):
            end = start + self.chunk_size
            if end < len(text):
                space_pos = text.rfind(' ', start, end)
                if space_pos != -1 and space_pos > start:
                    end = space_pos
            chunk = text[start:end].strip()
            if chunk:
                chunks.append(chunk)
                metadata.append({
                    "chunk_id": f"chunk_{chunk_id}",
                    "text": chunk,  # ← сохраняем текст чанка!
                    "start_char": start,
                    "end_char": end,
                })
                chunk_id += 1
            start = end - self.chunk_overlap if end - self.chunk_overlap > start else end

        return chunks, metadata

    def add_document(self, file_path: str, doc_id: int) -> bool:
        try:
            text = self._read_text_from_file(file_path)
            if not text:
                return False

            chunks, metadata_list = self.process_document(text)

            # Добавляем doc_id в каждую запись
            for meta in metadata_list:
                meta["doc_id"] = doc_id

            embeddings = self.embedding_model.encode(chunks, show_progress_bar=False).tolist()
            self.vector_db.add_embeddings(embeddings, metadata_list)
            self.vector_db.save_index()
            return True
        except Exception as e:
            from flask import current_app
            current_app.logger.error(f"Error in add_document (doc_id={doc_id}): {e}")
            return False

    def search_similar(self, query: str, k: int = 3) -> List[Dict]:
        query_embedding = self.embedding_model.encode(query).tolist()
        _, metadata_list = self.vector_db.search_vectors(query_embedding, k=k)
        return metadata_list

    def augment_prompt(self, query: str, k: int = 3) -> str:
        similar_chunks = self.search_similar(query, k=k)
        context_parts = [item["text"] for item in similar_chunks if "text" in item]
        return "\n\n".join(context_parts) if context_parts else ""