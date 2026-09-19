"""Direct CTranslate2 inference using Argos/OpenNMT SentencePiece models."""
import os
import re
from models import find_model
from core import MemoryCache, normalize
from text_layout import sentence_units
from terms import clean_glossary, translate_terms


def split_for_model(text, tokenizer, limit=192):
    """Bound model work without discarding text or splitting a subword token."""
    output=[]
    for sentence in sentence_units(text):
        while len(tokenizer.encode(sentence,out_type=str))>limit:
            low,high=1,len(sentence)
            while low<high:
                mid=(low+high+1)//2
                if len(tokenizer.encode(sentence[:mid],out_type=str))<=limit: low=mid
                else: high=mid-1
            candidates=[m.end() for m in re.finditer(r'[\s,;、，；]',sentence[:low]) if m.end()>=low//2]
            cut=candidates[-1] if candidates else low
            output.append(sentence[:cut]); sentence=sentence[cut:]
        if sentence: output.append(sentence)
    return output


class Translator:
    def __init__(self):
        self.loaded = {}
        self.cache = MemoryCache(500)
        self.direct = find_model('m2m100') is not None
        self.glossary={}
        self.katakana=True
        self.term_cache=MemoryCache(500)

    def configure(self,glossary=None,katakana=True):
        glossary=clean_glossary(glossary)
        if self.glossary!=glossary or self.katakana!=katakana:
            self.glossary=glossary; self.katakana=bool(katakana); self.term_cache.clear()

    def _pair(self, text, pair, source=None):
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
        chunks = split_for_model(text,tokenizer)
        def infer(chunk, depth=0):
            tokens=tokenizer.encode(chunk,out_type=str)
            options={}
            if pair=='m2m100':
                # This Hugging Face conversion expects explicit source EOS.
                # Omitting it causes repeated words and missing sentence ends.
                tokens=['__'+source+'__']+tokens+['</s>']
                options['target_prefix']=[['__ko__']]
            result=engine.translate_batch([tokens],beam_size=4,
                length_penalty=1.0 if pair=='m2m100' else 0.2,
                replace_unknowns=True,max_input_length=0,max_decoding_length=512,**options)[0]
            hypothesis=result.hypotheses[0]
            if len(hypothesis)>=512:
                if len(chunk)<2 or depth>=8:
                    raise RuntimeError('번역 결과가 길이 제한에 도달했습니다.')
                middle=len(chunk)//2
                return infer(chunk[:middle],depth+1)+' '+infer(chunk[middle:],depth+1)
            if pair=='m2m100' and hypothesis[:1]==['__ko__']: hypothesis=hypothesis[1:]
            translated=tokenizer.decode(hypothesis).replace('▁',' ').strip()
            if not translated or re.search(r'[\u2047\ufffd]|<unk>',translated) or re.fullmatch(r'[?\s.!]+',translated):
                raise RuntimeError('번역 모델이 이 문장을 해석하지 못했습니다.')
            return translated
        return ' '.join(infer(chunk) for chunk in chunks).strip()

    def translate(self, text, source):
        text=normalize(text)
        if source=='keep': return text
        key=(source,text)
        result=self.term_cache.get(key)
        if result is None:
            result=translate_terms(text,source,self._translate_raw,self.glossary,self.katakana)
            self.term_cache.put(key,result)
        return result

    def _translate_raw(self, text, source):
        text=normalize(text)
        if source=='keep': return text
        key = (source, text)
        result = self.cache.get(key)
        if result is None:
            if self.direct:
                result=self._pair(text,'m2m100',source)
            else:
                intermediate = self._pair(text, source+'_en') if source != 'en' else text
                result = self._pair(intermediate, 'en_ko')
            self.cache.put(key, result)
        return result
