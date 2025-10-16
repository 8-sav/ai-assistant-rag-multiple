# app/services/vector_db.py

import os
import pickle
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
import faiss

class VectorDB:
    def __init__(self, index_path: str, embedding_model_name: str):
        self.index_path = index_path
        self.embedding_model_name = embedding_model_name
        self.embedding_model = SentenceTransformer(embedding_model_name)
        self.index = None
        self.metadata = []  # список метаданных, синхронизированный с индексом FAISS
        self.dimension = self.embedding_model.get_sentence_embedding_dimension()

    def initialize_index(self):
        """Загружает индекс с диска или создаёт новый."""
        index_file = os.path.join(self.index_path, 'index.faiss')
        meta_file = os.path.join(self.index_path, 'metadata.pkl')

        # ГАРАНТИРУЕМ, ЧТО ПАПКА СУЩЕСТВУЕТ
        Path(self.index_path).mkdir(parents=True, exist_ok=True)

        if os.path.exists(index_file) and os.path.exists(meta_file):
            self.index = faiss.read_index(index_file)
            with open(meta_file, 'rb') as f:
                self.metadata = pickle.load(f)
        else:
            # Создаём пустой индекс L2
            self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []

    def add_embeddings(self, embeddings: list, metadata: list):
        """Добавляет эмбеддинги и метаданные в индекс."""
        if len(embeddings) != len(metadata):
            raise ValueError("Количество эмбеддингов и метаданных должно совпадать")

        embeddings_np = np.array(embeddings, dtype=np.float32)
        faiss.normalize_L2(embeddings_np)  # опционально, если используется косинусное расстояние
        self.index.add(embeddings_np)
        self.metadata.extend(metadata)

    def search_vectors(self, query_embedding: list, k: int = 3):
        """Ищет k ближайших соседей по эмбеддингу запроса."""
        if self.index is None or self.index.ntotal == 0:
            return [], []

        query_np = np.array([query_embedding], dtype=np.float32)
        faiss.normalize_L2(query_np)  # опционально
        distances, indices = self.index.search(query_np, k)

        results_meta = []
        results_distances = []

        for i, idx in enumerate(indices[0]):
            if idx < len(self.metadata):
                results_meta.append(self.metadata[idx])
                results_distances.append(float(distances[0][i]))

        return results_distances, results_meta

    def save_index(self):
        """Сохраняет индекс и метаданные на диск."""
        index_file = os.path.join(self.index_path, 'index.faiss')
        meta_file = os.path.join(self.index_path, 'metadata.pkl')

        faiss.write_index(self.index, index_file)
        with open(meta_file, 'wb') as f:
            pickle.dump(self.metadata, f)

    def load_index(self):
        """Явная загрузка индекса (обычно вызывается через initialize_index)."""
        self.initialize_index()