import numpy as np
import threading
import json

# We import sentence_transformers inside a lazy loader or class,
# to avoid loading overhead when initializing modules.
class SBERTModelManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super(SBERTModelManager, cls).__new__(cls)
                    cls._instance._initialized = False
        return cls._instance
        
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        if self._initialized:
            return
            
        self.model_name = model_name
        self.model = None
        self._load_lock = threading.Lock()
        self._initialized = True
        
    def get_model(self):
        """
        Thread-safe lazy loading of the SentenceTransformer model.
        """
        import os
        if os.environ.get('DISABLE_SBERT', 'False') == 'True':
            return None
            
        if self.model is None:
            with self._load_lock:
                if self.model is None:
                    try:
                        # Lazy import to speed up startup of django management commands
                        from sentence_transformers import SentenceTransformer
                        # This will automatically download and cache the model locally
                        self.model = SentenceTransformer(self.model_name)
                    except Exception as e:
                        print(f"SBERT model loading failed: {str(e)}. Falling back to mock embeddings.")
                        self.model = None
        return self.model

    def get_embedding(self, text):
        """
        Generates a 384-dimensional embedding for the input text.
        Returns a 1D numpy array.
        """
        if not text or not text.strip():
            # Return zero vector if text is empty
            return np.zeros(384, dtype=np.float32)
            
        model = self.get_model()
        if model is None:
            return np.zeros(384, dtype=np.float32)
            
        try:
            # Encode returns a numpy array
            embedding = model.encode(text, convert_to_numpy=True)
            return embedding
        except Exception as e:
            print(f"SBERT encoding failed: {str(e)}. Returning zero vector.")
            return np.zeros(384, dtype=np.float32)

    def serialize_embedding(self, embedding):
        """
        Converts embedding numpy array into JSON string for DB storage.
        """
        return json.dumps(embedding.tolist())

    def deserialize_embedding(self, json_str):
        """
        Converts JSON string from DB back to numpy array.
        """
        if not json_str:
            return np.zeros(384, dtype=np.float32)
        return np.array(json.loads(json_str), dtype=np.float32)

    def calculate_similarity(self, embedding1, embedding2):
        """
        Calculates cosine similarity between two 1D embeddings.
        Returns a float score between 0.0 and 1.0.
        """
        # Ensure they are numpy arrays
        if isinstance(embedding1, list):
            embedding1 = np.array(embedding1)
        if isinstance(embedding2, list):
            embedding2 = np.array(embedding2)
            
        norm1 = np.linalg.norm(embedding1)
        norm2 = np.linalg.norm(embedding2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
            
        dot_product = np.dot(embedding1, embedding2)
        similarity = dot_product / (norm1 * norm2)
        
        # Handle precision adjustments for exact matches
        if np.isclose(similarity, 1.0, atol=1e-5):
            return 1.0
            
        # Clip to [0, 1] range to avoid floating point precision issues
        return float(np.clip(similarity, 0.0, 1.0))
