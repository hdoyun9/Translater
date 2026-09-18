"""Direct CTranslate2 inference using Argos/OpenNMT SentencePiece models."""
import os
from models import find_model
from core import MemoryCache


class Translator:
    def __init__(self):
        self.loaded = {}
        self.cache = MemoryCache(500)

    def _pair(self, text, pair):
        if pair not in self.loaded:
            import ctranslate2
            import sentencepiece
            path = find_model(pair)
            if path is None:
                raise RuntimeError('번역 모델이 없습니다: ' + pair)
            engine = ctranslate2.Translator(str(path/'model'), device='cpu',
                       compute_type='int8', inter_threads=1,
                       intra_threads=min(4, os.cpu_count() or 2))
            # Python handles Unicode Windows paths; SentencePiece's native file
            # loader can fail with "Illegal byte sequence" on Korean paths.
            tokenizer = sentencepiece.SentencePieceProcessor(
                model_proto=(path/'sentencepiece.model').read_bytes())
            self.loaded[pair] = (engine, tokenizer)
        engine, tokenizer = self.loaded[pair]
        tokens = tokenizer.encode(text, out_type=str)
        # Bound work without silently discarding the remainder of a long OCR line.
        chunks = [tokens[i:i+160] for i in range(0, len(tokens), 160)]
        results = engine.translate_batch(chunks, beam_size=2, max_decoding_length=256)
        return ' '.join(tokenizer.decode(r.hypotheses[0]) for r in results).strip()

    def translate(self, text, source):
        key = (source, text)
        result = self.cache.get(key)
        if result is None:
            intermediate = self._pair(text, source+'_en') if source != 'en' else text
            result = self._pair(intermediate, 'en_ko')
            self.cache.put(key, result)
        return result
